import logging
from datetime import datetime
from typing import Tuple, List
from pathlib import PurePosixPath

from dropbox import Dropbox
from dropbox.files import FileMetadata, FolderMetadata

from app.services.auth_service import auth_service
from app.services.pubsub_mgr import pubsub_mgr
from app.database import bulk_upsert

logger = logging.getLogger(__name__)


def get_parent_path(path: str) -> str:
    """Extract parent path from a given path."""
    if not path or path == "/":
        return ""
    parent = str(PurePosixPath(path).parent)
    return parent if parent != "." else ""


def classify_entries(entries: list) -> Tuple[List[dict], List[dict]]:
    """
    Classify Dropbox entries into files and folders.

    Returns:
        Tuple of (files_list, folders_list) as dictionaries ready for DB
    """
    files = []
    folders = []

    for entry in entries:
        base_item = {
            "id": entry.id,
            "name": entry.name,
            "path_display": entry.path_display,
            "path_lower": entry.path_lower,
            "parent_path_lower": get_parent_path(entry.path_lower),
            "indexed_at": datetime.utcnow()
        }

        if isinstance(entry, FileMetadata):
            files.append({
                **base_item,
                "type": "file",
                "size": entry.size,
                "content_hash": getattr(entry, 'content_hash', None),
                "client_modified": entry.client_modified
            })
        elif isinstance(entry, FolderMetadata):
            folders.append({
                **base_item,
                "type": "folder",
                "size": 0,
                "content_hash": None,
                "client_modified": None
            })

    return files, folders


async def process_folder_task(path: str) -> dict:
    """
    Main worker logic: Process a single folder task.

    1. Get fresh token from auth microservice
    2. List folder contents from Dropbox API
    3. Bulk UPSERT files and folders to database
    4. Publish subfolder tasks to Pub/Sub for fan-out

    Args:
        path: Dropbox folder path to process (e.g., "/" or "/Documents")

    Returns:
        Dictionary with processing statistics
    """
    logger.info(f"Starting to process folder: {path}")

    # 1. Get fresh Dropbox token
    token = await auth_service.get_valid_token()
    dbx = Dropbox(token)

    # 2. List folder contents with pagination
    all_entries = []

    # Handle root path (Dropbox API uses empty string for root)
    list_path = "" if path == "/" else path

    result = dbx.files_list_folder(list_path)
    all_entries.extend(result.entries)

    # Handle pagination
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        all_entries.extend(result.entries)
        logger.debug(f"Fetched {len(all_entries)} entries so far for {path}")

    # 3. Classify and prepare data
    files_buffer, folders_buffer = classify_entries(all_entries)

    # 4. Bulk UPSERT to database (idempotent)
    all_items = files_buffer + folders_buffer
    if all_items:
        bulk_upsert(all_items)

    # 5. Fan-out: Publish subfolder tasks to Pub/Sub
    published_count = 0
    for folder in folders_buffer:
        pubsub_mgr.publish_folder_task(folder["path_display"])
        published_count += 1

    stats = {
        "path": path,
        "files_count": len(files_buffer),
        "folders_count": len(folders_buffer),
        "tasks_published": published_count
    }

    logger.info(
        f"Processed {path}: "
        f"{stats['files_count']} files, "
        f"{stats['folders_count']} folders, "
        f"{stats['tasks_published']} new tasks published"
    )

    return stats
