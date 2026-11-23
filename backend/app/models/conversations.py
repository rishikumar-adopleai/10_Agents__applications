"""Conversations, Messages, Attempts and Suppression Models."""

from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import BaseModel, OrganizationScopedMixin


class Conversation(BaseModel, OrganizationScopedMixin):
    """Conversation thread with a lead."""

    __tablename__ = "conversations"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(
        String(50), default="sms", nullable=False
    )  # sms, web, email
    status: Mapped[str] = mapped_column(
        String(50), default="active", nullable=False
    )  # active, human_takeover, closed, paused
    is_human_takeover: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )  # Optimistic concurrency lock
    assigned_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(BaseModel, OrganizationScopedMixin):
    """Inbound or outbound conversational message."""

    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # inbound, outbound
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Ingestion & Deduplication
    deduplication_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(50), default="received", nullable=False
    )  # received, approved, sent, delivered, failed
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class OutreachAttempt(BaseModel, OrganizationScopedMixin):
    """Tracks logical outreach attempts to prevent 4th unanswered attempts."""

    __tablename__ = "outreach_attempts"

    contact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3 (max 3 allowed)
    channel: Mapped[str] = mapped_column(String(50), default="sms", nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="sent", nullable=False
    )  # sent, answered, bounced, failed
    message_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class SuppressionEntry(BaseModel, OrganizationScopedMixin):
    """Hard suppression / opt-out registry across all campaigns and agents."""

    __tablename__ = "suppression_entries"

    contact_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # opt_out, negative_reply, bot_response, competitor, manual
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cannot_be_cleared_by_campaign: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
