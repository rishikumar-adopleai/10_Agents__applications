"""Inbound Messaging Webhook Ingest and Processing for Pipeline 4."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger
from backend.app.db.session import get_db
from backend.app.schemas.common import StandardResponse
from backend.app.schemas.conversations import InboundEmailWebhookPayload, InboundWebhookPayload
from backend.app.services.pipeline4_engine import Pipeline4Engine

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/sms", response_model=StandardResponse[dict], status_code=status.HTTP_200_OK)
async def inbound_sms_webhook(
    payload: InboundWebhookPayload,
    session: AsyncSession = Depends(get_db),
):
    """
    Ingest, deduplicate, persist, and process inbound SMS message through Pipeline 4's 5 nodes:
    Node 1: Ingest (dedup & atomic persistence)
    Node 2: Customer Context (contact & thread resolution)
    Node 3: Safety + Sentiment (STOP / rejection / bot check & LLM sentiment)
    Node 4: Memory (load customer history, P2 research, P3 demo refs, knowledge facts)
    Node 5: Intent + Action + Draft (calendar booking, demo lookup, draft generation)
    """
    logger.info(f"[Webhooks] Inbound SMS from {payload.sender_phone}: '{payload.body[:60]}'")
    engine = Pipeline4Engine(session)
    result = await engine.process_inbound_message(
        sender=payload.sender_phone,
        recipient=payload.recipient_phone,
        body=payload.body,
        channel="sms",
        provider=payload.provider,
        provider_message_id=payload.message_id,
        auto_dispatch=False,
    )

    return StandardResponse(
        data=result,
        message="Inbound SMS processed by 24/7 Lead Responder Agent",
    )


@router.post("/email", response_model=StandardResponse[dict], status_code=status.HTTP_200_OK)
async def inbound_email_webhook(
    payload: InboundEmailWebhookPayload,
    session: AsyncSession = Depends(get_db),
):
    """
    Ingest and process inbound Email notifications from Microsoft Graph / Outlook.
    Executes all 5 nodes of Pipeline 4.
    """
    logger.info(f"[Webhooks] Inbound Email from {payload.sender_email}: '{payload.body[:60]}'")
    engine = Pipeline4Engine(session)
    result = await engine.process_inbound_message(
        sender=payload.sender_email,
        recipient=payload.recipient_email or "sales@adople.ai",
        body=payload.body,
        channel="email",
        provider=payload.provider or "microsoft_graph",
        provider_message_id=payload.message_id,
        auto_dispatch=False,
    )

    return StandardResponse(
        data=result,
        message="Inbound email processed by 24/7 Lead Responder Agent",
    )
