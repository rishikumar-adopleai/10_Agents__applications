"""Meeting Booking, Proposal, and Pipeline 4 Execution Models."""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import BaseModel, OrganizationScopedMixin


class MeetingBooking(BaseModel, OrganizationScopedMixin):
    """Confirmed or requested calendar meeting with a lead."""

    __tablename__ = "meeting_bookings"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    organizer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    attendee_email: Mapped[str] = mapped_column(String(255), nullable=False)
    attendee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    start_time: Mapped[str] = mapped_column(String(50), nullable=False)  # ISO 8601 UTC
    end_time: Mapped[str] = mapped_column(String(50), nullable=False)    # ISO 8601 UTC
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)

    # Booking state conforming to Section 8.3 B8 of the Specification:
    # meeting_requested, checking_availability, requested_slot_unavailable,
    # alternatives_offered, waiting_for_customer_selection, customer_confirmed,
    # booking_in_progress, booking_confirmed, booking_failed, booking_unknown,
    # rescheduling, cancellation_requested, cancelled, human_review_required
    status: Mapped[str] = mapped_column(String(50), default="meeting_requested", nullable=False, index=True)

    outlook_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    teams_join_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    offered_slots: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-serialized alternative slots
    selected_slot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-serialized selected slot
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_booked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MeetingProposal(BaseModel, OrganizationScopedMixin):
    """Pending proposed slots offered to customer awaiting confirmation."""

    __tablename__ = "meeting_proposals"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    requested_slot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON {start, end, display, requested_time}
    offered_slots: Mapped[str] = mapped_column(Text, nullable=False)            # JSON list of alternative slots
    selected_slot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON confirmed slot
    status: Mapped[str] = mapped_column(String(50), default="offered", nullable=False)  # offered, confirmed, expired, superseded
    expires_at: Mapped[str] = mapped_column(String(50), nullable=False)


class NodeExecutionLog(BaseModel, OrganizationScopedMixin):
    """Telemetry record capturing each of the 5 Pipeline 4 internal processing nodes."""

    __tablename__ = "node_execution_logs"

    message_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    contact_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(50), default="sms", nullable=False)

    node1_ingest: Mapped[Optional[str]] = mapped_column(Text, nullable=True)       # JSON
    node2_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)      # JSON
    node3_safety: Mapped[Optional[str]] = mapped_column(Text, nullable=True)       # JSON
    node4_memory: Mapped[Optional[str]] = mapped_column(Text, nullable=True)       # JSON
    node5_intent_draft: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON

    approval_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    send_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
