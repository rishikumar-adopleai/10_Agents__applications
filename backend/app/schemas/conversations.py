"""Conversations, Messages and Inbound Payload Schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class MessageBase(BaseModel):
    direction: str  # inbound, outbound
    sender: str
    recipient: str
    body: str


class MessageCreate(MessageBase):
    external_id: Optional[str] = None


class MessageResponse(MessageBase):
    id: str
    conversation_id: str
    organization_id: str
    status: str
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: str
    organization_id: str
    account_id: str
    contact_id: str
    channel: str
    status: str
    is_human_takeover: bool
    version: int
    assigned_user_id: Optional[str] = None
    messages: List[MessageResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InboundWebhookPayload(BaseModel):
    provider: str
    message_id: str
    sender_phone: str
    recipient_phone: str
    body: str
    timestamp: Optional[str] = None


class InboundEmailWebhookPayload(BaseModel):
    provider: Optional[str] = "microsoft_graph"
    message_id: str
    sender_email: str
    recipient_email: Optional[str] = "sales@adople.ai"
    subject: Optional[str] = ""
    body: str
    timestamp: Optional[str] = None
