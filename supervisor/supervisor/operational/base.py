"""Operational database Base.

This is a separate SQLAlchemy declarative base for operational tables.
Operational tables are stored in per-supervisor databases, not the central DB.
"""

from sqlalchemy.orm import declarative_base

# Separate Base for operational models - these tables live in per-supervisor DBs
OperationalBase = declarative_base()
