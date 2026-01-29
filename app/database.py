import logging
from datetime import datetime
from typing import List

from sqlalchemy import (
    create_engine,
    Column,
    String,
    BigInteger,
    Text,
    DateTime,
    Index
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DropboxItem(Base):
    """Model for Dropbox file/folder metadata."""

    __tablename__ = "dropbox_items"

    id = Column(String(255), primary_key=True)
    name = Column(String(512), nullable=False)
    path_display = Column(Text, nullable=False)
    path_lower = Column(Text, nullable=False, unique=True)
    type = Column(String(20), nullable=False)
    parent_path_lower = Column(Text, nullable=True)
    size = Column(BigInteger, default=0)
    content_hash = Column(String(128), nullable=True)
    client_modified = Column(DateTime, nullable=True)
    indexed_at = Column(DateTime, default=datetime.utcnow)
    web_url = Column(Text, nullable=True)
    
    __table_args__ = (
        Index('idx_parent_path', 'parent_path_lower'),
        Index('idx_type', 'type'),
    )


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def bulk_upsert(items: List[dict]):
    """
    Insert or update items in bulk (idempotent operation).
    Uses PostgreSQL ON CONFLICT for upsert.
    """
    if not items:
        return

    with SessionLocal() as session:
        stmt = insert(DropboxItem).values(items)

        update_dict = {
            'name': stmt.excluded.name,
            'path_display': stmt.excluded.path_display,
            'type': stmt.excluded.type,
            'parent_path_lower': stmt.excluded.parent_path_lower,
            'size': stmt.excluded.size,
            'content_hash': stmt.excluded.content_hash,
            'client_modified': stmt.excluded.client_modified,
            'indexed_at': datetime.utcnow()
        }

        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['path_lower'],
            set_=update_dict
        )

        session.execute(upsert_stmt)
        session.commit()
        logger.info(f"Upserted {len(items)} items to database")
