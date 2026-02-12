"""
User profile model for Supabase authentication integration.

This model represents a profiles table that references Supabase's auth.users table.
Authentication is handled entirely by Supabase client-side. This table stores
additional user profile information.

Design:
- Primary key (id) is the Supabase auth.users UUID (as string for compatibility)
- No password_hash or auth-related fields (Supabase handles this)
- Profile data only (display name, avatar, preferences, etc.)
- Foreign key relationship to auth.users implicit via matching UUID
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserProfile(Base):
    """
    User profile table referencing Supabase auth.users.

    The id field matches the UUID from Supabase's auth.users table.
    This is a profile/extension table, not an auth table.
    """

    __tablename__ = "profiles"

    # Primary key - matches Supabase auth.users UUID
    # Supabase auth.users.id is UUID type, we store as string for compatibility
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        nullable=False,
        comment="Supabase auth.users UUID (as string)"
    )

    # Profile fields
    display_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="User's display name (public)"
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to user's avatar image (typically Supabase Storage)"
    )

    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User's bio/description"
    )

    # Additional preferences
    preferences: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON string for additional user preferences/settings"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Profile creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Profile last update timestamp"
    )

    # Table constraints and indexes
    __table_args__ = (
        Index("idx_profiles_id", "id"),
        Index("idx_profiles_display_name", "display_name"),
        {
            "comment": "User profiles table - extends Supabase auth.users with additional profile data"
        },
    )

    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id}, display_name={self.display_name})>"


# Keep User as an alias for backward compatibility
# But the canonical model is now UserProfile
User = UserProfile

__all__ = ["UserProfile", "User"]
