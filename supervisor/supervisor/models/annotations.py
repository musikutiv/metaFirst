"""File annotation model for one-file → many-samples metadata patterns."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from supervisor.database import Base


class FileAnnotation(Base):
    """Generic annotation record attaching metadata to a measurement file.

    Supports the one-file → many-samples pattern: multiple rows may reference
    the same RawDataItem, each optionally linked to a distinct Sample.

    - ``key`` is a protocol-defined string (set via the project RDMP) that
      names what the annotation represents, e.g. ``"observation"`` or
      ``"sample_map"``.  No technology-specific keys are defined here.
    - ``index_json`` carries optional protocol-defined positional or
      dimensional context for the annotation within the file (e.g. order
      within a measurement sequence).  NULL means the annotation applies to
      the file as a whole.
    - ``value_json`` / ``value_text`` hold the annotation payload.
      ``value_text`` is a searchable plain-text representation of the same
      content.
    - ``sample_id`` is nullable: NULL means the annotation is file-level
      rather than sample-level.

    No uniqueness constraint is placed on (raw_data_item_id, sample_id, key)
    because the same key may validly appear multiple times for a single file
    (e.g. multiple observations at different index_json positions).
    """

    __tablename__ = "file_annotations"

    id = Column(Integer, primary_key=True, index=True)
    raw_data_item_id = Column(
        Integer,
        ForeignKey("raw_data_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NULL → file-level annotation; non-NULL → annotation for a specific sample
    sample_id = Column(
        Integer,
        ForeignKey("samples.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Protocol-defined annotation key; validated against RDMP at the API layer
    key = Column(String(255), nullable=False)
    # Optional coordinates/dimensions within the file (protocol-defined schema)
    index_json = Column(JSON, nullable=True)
    value_json = Column(JSON, nullable=True)
    value_text = Column(Text, nullable=True)  # Searchable plain-text representation
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    raw_data_item = relationship("RawDataItem")
    sample = relationship("Sample")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        # Primary lookup: all annotations for a file, optionally filtered by key
        Index("ix_file_annotations_item_key", "raw_data_item_id", "key"),
        # Secondary lookup: all sample-linked annotations for a file
        Index("ix_file_annotations_item_sample", "raw_data_item_id", "sample_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<FileAnnotation(id={self.id}, raw_data_item_id={self.raw_data_item_id}, "
            f"sample_id={self.sample_id}, key='{self.key}')>"
        )
