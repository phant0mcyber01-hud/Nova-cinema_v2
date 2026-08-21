"""One import line for everything a router needs from the core layer."""
from backend.core.db import get_db
from backend.core.security import admin_required, current_user

__all__ = ["admin_required", "current_user", "get_db"]
