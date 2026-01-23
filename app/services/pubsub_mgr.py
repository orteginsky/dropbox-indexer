import json
import logging

from google.cloud import pubsub_v1

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PubSubManager:
    """Wrapper for Google Cloud Pub/Sub operations."""

    def __init__(self):
        self.project_id = settings.gcp_project_id
        self.topic_name = settings.pubsub_topic_name
        self._publisher = None

    @property
    def publisher(self) -> pubsub_v1.PublisherClient:
        """Lazy initialization of publisher client."""
        if self._publisher is None:
            self._publisher = pubsub_v1.PublisherClient()
        return self._publisher

    @property
    def topic_path(self) -> str:
        """Full topic path."""
        return self.publisher.topic_path(self.project_id, self.topic_name)

    def publish_message(self, data: dict) -> str:
        """
        Publish a message to the Pub/Sub topic.

        Args:
            data: Dictionary with message payload (e.g., {"path": "/folder"})

        Returns:
            Message ID from Pub/Sub
        """
        message_bytes = json.dumps(data).encode("utf-8")

        future = self.publisher.publish(self.topic_path, message_bytes)
        message_id = future.result()

        logger.debug(f"Published message {message_id} to {self.topic_name}: {data}")
        return message_id

    def publish_folder_task(self, path: str) -> str:
        """
        Convenience method to publish a folder crawl task.

        Args:
            path: Dropbox folder path to crawl

        Returns:
            Message ID from Pub/Sub
        """
        return self.publish_message({"path": path})

    def publish_batch(self, paths: list[str]) -> list[str]:
        """
        Publish multiple folder tasks in batch.

        Args:
            paths: List of Dropbox folder paths

        Returns:
            List of message IDs
        """
        message_ids = []
        for path in paths:
            msg_id = self.publish_folder_task(path)
            message_ids.append(msg_id)

        logger.info(f"Published {len(message_ids)} tasks to Pub/Sub")
        return message_ids


pubsub_mgr = PubSubManager()
