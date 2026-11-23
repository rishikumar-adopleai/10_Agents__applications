"""Pipeline 4: 24/7 Lead Responder Agent REST Endpoints."""

import json
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.core.rbac import CurrentUser
from backend.app.db.session import get_db
from backend.app.models.conversations import (
    Conversation,
    Message,
    SuppressionEntry,
)
from backend.app.models.governance import ApprovalItem
from backend.app.models.meetings import MeetingBooking, MeetingProposal, NodeExecutionLog
from backend.app.models.sales import Account, Contact
from backend.app.schemas.common import StandardResponse
from backend.app.services.pipeline4_engine import Pipeline4Engine

router = APIRouter(prefix="/responder", tags=["pipeline4_lead_responder"])


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------
class InboundMessagePayload(BaseModel):
    sender: str
    recipient: Optional[str] = "sales@adople.ai"
    body: str
    channel: Optional[str] = "sms"  # sms or email
    provider: Optional[str] = "api_gateway"
    provider_message_id: Optional[str] = None
    auto_dispatch: Optional[bool] = False


class ApproveReplyPayload(BaseModel):
    edited_content: Optional[str] = None


class RescheduleMeetingPayload(BaseModel):
    new_start_time: str
    new_end_time: str
    timezone: Optional[str] = "UTC"


class CancelMeetingPayload(BaseModel):
    reason: Optional[str] = "Customer requested cancellation"


class SimulateScenarioPayload(BaseModel):
    scenario: Optional[str] = None
    scenario_type: Optional[str] = None
    sender: Optional[str] = None
    sender_email: Optional[str] = None
    sender_phone: Optional[str] = None
    body: Optional[str] = None
    channel: Optional[str] = "sms"


# -----------------------------------------------------------------------------
# 1. Pipeline 4 Dashboard Endpoints
# -----------------------------------------------------------------------------
@router.get("/dashboard", response_model=StandardResponse[Dict[str, Any]])
async def get_responder_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve operational metrics, sentiment breakdown, and provider health for Pipeline 4."""
    org_id = current_user.organization_id

    # Messages Count
    msg_res = await session.execute(select(Message).where(Message.organization_id == org_id))
    all_msgs = msg_res.scalars().all()
    inbound_msgs = [m for m in all_msgs if m.direction == "inbound"]
    outbound_msgs = [m for m in all_msgs if m.direction == "outbound"]

    # Active Conversations
    conv_res = await session.execute(select(Conversation).where(Conversation.organization_id == org_id))
    all_convs = conv_res.scalars().all()
    active_convs = [c for c in all_convs if c.status == "active"]
    human_takeovers = [c for c in all_convs if c.is_human_takeover or c.status == "human_takeover"]

    # Suppression & Opt-outs
    sup_res = await session.execute(select(SuppressionEntry).where(SuppressionEntry.organization_id == org_id))
    all_sups = sup_res.scalars().all()
    opt_outs = [s for s in all_sups if s.reason == "opt_out"]
    negative_rejections = [s for s in all_sups if s.reason == "negative_reply"]

    # Meetings & Bookings
    mtg_res = await session.execute(select(MeetingBooking).where(MeetingBooking.organization_id == org_id))
    all_mtgs = mtg_res.scalars().all()
    confirmed_mtgs = [m for m in all_mtgs if m.status == "booking_confirmed"]
    requested_mtgs = [m for m in all_mtgs if m.status in ("meeting_requested", "alternatives_offered")]
    failed_mtgs = [m for m in all_mtgs if m.status == "booking_failed"]

    # Pending Approvals
    appr_res = await session.execute(
        select(ApprovalItem).where(
            ApprovalItem.organization_id == org_id,
            ApprovalItem.artifact_type == "lead_reply",
            ApprovalItem.status == "pending",
        )
    )
    pending_approvals = appr_res.scalars().all()

    # Telemetry Sentiment stats from NodeExecutionLogs
    log_res = await session.execute(
        select(NodeExecutionLog).where(NodeExecutionLog.organization_id == org_id).limit(100)
    )
    logs = log_res.scalars().all()
    pos_count = 0
    neg_count = 0
    neut_count = 0
    auto_count = 0
    unsub_count = 0
    for log_item in logs:
        try:
            safety = json.loads(log_item.node3_safety or "{}")
            sent = safety.get("sentiment", "neutral")
            if sent == "positive":
                pos_count += 1
            elif sent == "negative":
                neg_count += 1
            elif sent == "automated":
                auto_count += 1
            elif sent == "unsubscribe":
                unsub_count += 1
            else:
                neut_count += 1
        except Exception:
            neut_count += 1

    # Provider Health
    engine = Pipeline4Engine(session)
    calendar_health = await engine.calendar_adapter.check_health()
    llm_health = await engine.llm_gateway.check_health()
    mail_health = await engine.mail_adapter.check_health()
    sms_health = await engine.sms_adapter.check_health()

    avg_latency = int(sum(l.total_latency_ms for l in logs) / max(len(logs), 1))
    return StandardResponse(
        data={
            "total_inbound_messages": len(inbound_msgs),
            "total_outbound_messages": len(outbound_msgs),
            "active_conversations": len(active_convs),
            "total_active_conversations": len(active_convs),
            "human_owned_conversations": len(human_takeovers),
            "human_takeovers_active": len(human_takeovers),
            "pending_approvals_count": len(pending_approvals),
            "confirmed_meetings_count": len(confirmed_mtgs),
            "requested_meetings_count": len(requested_mtgs),
            "failed_bookings_count": len(failed_mtgs),
            "unsubscribe_count": len(opt_outs),
            "negative_rejections_count": len(negative_rejections),
            "average_latency_ms": avg_latency,
            "sentiment_distribution": {
                "positive": pos_count,
                "negative": neg_count,
                "neutral": neut_count,
                "automated": auto_count,
                "unsubscribe": unsub_count,
            },
            "sentiment_breakdown": {
                "positive": pos_count,
                "negative": neg_count,
                "neutral": neut_count,
                "automated": auto_count,
                "unsubscribe": unsub_count,
            },
            "meeting_stats": {
                "confirmed_meetings": len(confirmed_mtgs),
                "pending_proposals": len(requested_mtgs),
                "auto_booked_rate": f"{(len(confirmed_mtgs) / max(len(confirmed_mtgs) + len(requested_mtgs), 1)) * 100:.0f}%",
            },
            "provider_health": {
                "microsoft_graph": calendar_health.status,
                "microsoft_calendar": calendar_health.status,
                "microsoft_outlook": mail_health.status,
                "sms_gateway": sms_health.status,
                "sms_provider": sms_health.status,
                "llm_gateway": llm_health.status,
                "organizer_mailbox": engine.calendar_adapter.organizer_email,
            },
        },
        message="Lead Responder Dashboard metrics loaded",
    )


# -----------------------------------------------------------------------------
# 2. Unified Inbox Endpoints
# -----------------------------------------------------------------------------
@router.get("/inbox", response_model=StandardResponse[List[Dict[str, Any]]])
async def list_unified_inbox(
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all lead conversation threads with latest messages, sentiment, and intent."""
    org_id = current_user.organization_id

    stmt = (
        select(Conversation)
        .where(Conversation.organization_id == org_id)
        .order_by(desc(Conversation.updated_at))
    )
    res = await session.execute(stmt)
    conversations = res.scalars().all()

    inbox_items = []
    for c in conversations:
        # Load contact & account
        con_res = await session.execute(select(Contact).where(Contact.id == c.contact_id))
        contact = con_res.scalars().first()

        acc_res = await session.execute(select(Account).where(Account.id == c.account_id))
        account = acc_res.scalars().first()

        # Load latest message
        m_stmt = (
            select(Message)
            .where(Message.conversation_id == c.id)
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        m_res = await session.execute(m_stmt)
        latest_msg = m_res.scalars().first()

        # Load pending approval item
        appr_stmt = (
            select(ApprovalItem)
            .where(
                ApprovalItem.artifact_id == c.id,
                ApprovalItem.status == "pending",
            )
            .order_by(desc(ApprovalItem.created_at))
            .limit(1)
        )
        appr_res = await session.execute(appr_stmt)
        pending_appr = appr_res.scalars().first()

        # Load confirmed meeting
        mtg_stmt = (
            select(MeetingBooking)
            .where(MeetingBooking.conversation_id == c.id, MeetingBooking.status == "booking_confirmed")
            .limit(1)
        )
        mtg_res = await session.execute(mtg_stmt)
        meeting = mtg_res.scalars().first()

        # Extract sentiment & intent from pending approval or latest message
        sentiment = "neutral"
        intent = "general_inquiry"
        if pending_appr and pending_appr.source_evidence:
            ev = pending_appr.source_evidence
            intent = ev.get("primary_intent", intent)

        latest_body = latest_msg.body if latest_msg else "No messages yet"
        item = {
            "conversation_id": c.id,
            "channel": c.channel,
            "status": c.status,
            "is_human_takeover": c.is_human_takeover,
            "contact_id": c.contact_id,
            "contact_name": f"{contact.first_name} {contact.last_name}".strip() if contact else "Inbound Lead",
            "contact_email": contact.email if contact else None,
            "contact_phone": contact.phone if contact else None,
            "company_name": account.name if account else "Enterprise Prospect",
            "latest_message": latest_body,
            "last_message_snippet": latest_body[:120] if latest_body else "No messages yet",
            "latest_message_direction": latest_msg.direction if latest_msg else "none",
            "last_activity": str(latest_msg.created_at if latest_msg else c.updated_at),
            "last_message_time": str(latest_msg.created_at if latest_msg else c.updated_at),
            "sentiment": sentiment,
            "intent": intent,
            "has_pending_approval": pending_appr is not None,
            "pending_draft": pending_appr.draft_content if pending_appr else None,
            "approval_id": pending_appr.id if pending_appr else None,
            "confirmed_meeting_time": meeting.start_time if meeting else None,
            "teams_join_url": meeting.teams_join_url if meeting else None,
        }

        # Filtering
        if channel and channel.lower() != "all" and item["channel"].lower() != channel.lower():
            continue
        if status and status.lower() != "all":
            if status == "human_takeover" and not item["is_human_takeover"]:
                continue
            if status == "pending_approval" and not item["has_pending_approval"]:
                continue
            if status == "active" and item["status"] != "active":
                continue

        inbox_items.append(item)

    return StandardResponse(data=inbox_items, message="Unified inbox threads loaded")


@router.post("/sync-inbox", response_model=StandardResponse[Dict[str, Any]])
async def sync_inbox_replies(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Poll Microsoft Outlook inbox via Microsoft Graph and ingest all incoming lead replies."""
    engine = Pipeline4Engine(session)
    result = await engine.sync_email_inbox(organization_id=current_user.organization_id)
    return StandardResponse(
        data=result,
        message=result.get("message", "Inbox sync completed"),
    )


# -----------------------------------------------------------------------------
# 3. Conversation Detail Endpoint
# -----------------------------------------------------------------------------
@router.get("/conversations/{conversation_id}", response_model=StandardResponse[Dict[str, Any]])
async def get_conversation_detail(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve full conversation thread, messages, research brief, demo context, and pending draft."""
    org_id = current_user.organization_id

    conv_res = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.organization_id == org_id)
    )
    conv = conv_res.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Messages in chronological order
    m_res = await session.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    messages = [
        {
            "id": m.id,
            "direction": m.direction,
            "sender": m.sender,
            "recipient": m.recipient,
            "body": m.body,
            "status": m.status,
            "is_verified": m.is_verified,
            "created_at": str(m.created_at),
        }
        for m in m_res.scalars().all()
    ]

    # Contact & Account info
    c_res = await session.execute(select(Contact).where(Contact.id == conv.contact_id))
    contact = c_res.scalars().first()

    a_res = await session.execute(select(Account).where(Account.id == conv.account_id))
    account = a_res.scalars().first()

    # Pending Approval Item
    appr_res = await session.execute(
        select(ApprovalItem)
        .where(ApprovalItem.artifact_id == conversation_id, ApprovalItem.status == "pending")
        .order_by(desc(ApprovalItem.created_at))
    )
    pending_appr = appr_res.scalars().first()

    # Active Meeting Proposal
    prop_res = await session.execute(
        select(MeetingProposal)
        .where(MeetingProposal.conversation_id == conversation_id, MeetingProposal.status == "offered")
        .order_by(desc(MeetingProposal.created_at))
    )
    proposal = prop_res.scalars().first()

    # Confirmed Meeting
    mtg_res = await session.execute(
        select(MeetingBooking)
        .where(MeetingBooking.conversation_id == conversation_id, MeetingBooking.status == "booking_confirmed")
        .order_by(desc(MeetingBooking.created_at))
    )
    meeting = mtg_res.scalars().first()

    # Pipeline 2 Research Brief & Pain Points
    engine = Pipeline4Engine(session)
    mem_context = await engine.node4_memory(
        contact=contact,
        account=account,
        conversation=conv,
        organization_id=org_id,
    )

    return StandardResponse(
        data={
            "conversation_id": conv.id,
            "channel": conv.channel,
            "status": conv.status,
            "is_human_takeover": conv.is_human_takeover,
            "conversation": {
                "id": conv.id,
                "channel": conv.channel,
                "status": conv.status,
                "is_human_takeover": conv.is_human_takeover,
                "created_at": str(conv.created_at),
            },
            "contact": {
                "id": contact.id if contact else None,
                "name": f"{contact.first_name} {contact.last_name}".strip() if contact else "Prospect",
                "email": contact.email if contact else None,
                "phone": contact.phone if contact else None,
                "title": contact.title if contact else None,
            },
            "account": {
                "id": account.id if account else None,
                "name": account.name if account else "Enterprise Prospect",
                "industry": account.industry if account else "Technology",
            },
            "messages": messages,
            "pending_approval": {
                "approval_id": pending_appr.id if pending_appr else None,
                "draft_content": pending_appr.draft_content if pending_appr else None,
                "source_evidence": pending_appr.source_evidence if pending_appr else None,
            } if pending_appr else None,
            "active_proposal": {
                "proposal_id": proposal.id if proposal else None,
                "offered_slots": json.loads(proposal.offered_slots) if proposal else [],
            } if proposal else None,
            "confirmed_meeting": {
                "booking_id": meeting.id if meeting else None,
                "start_time": meeting.start_time if meeting else None,
                "teams_join_url": meeting.teams_join_url if meeting else None,
                "outlook_event_id": meeting.outlook_event_id if meeting else None,
            } if meeting else None,
            "research_brief": mem_context.get("research_brief"),
            "marketplace_demos": mem_context.get("demo_products", [])[:2],
        },
        message="Conversation detail loaded successfully",
    )


# -----------------------------------------------------------------------------
# 4. Inbound Processing (Trigger all 5 Nodes)
# -----------------------------------------------------------------------------
@router.post("/inbound", response_model=StandardResponse[Dict[str, Any]])
async def process_inbound(
    payload: InboundMessagePayload,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Process an inbound customer SMS or email message through the full 5-Node Pipeline 4.
    """
    engine = Pipeline4Engine(session)
    result = await engine.process_inbound_message(
        sender=payload.sender,
        recipient=payload.recipient or "sales@adople.ai",
        body=payload.body,
        channel=payload.channel or "sms",
        provider=payload.provider or "api_gateway",
        provider_message_id=payload.provider_message_id,
        organization_id=current_user.organization_id,
        auto_dispatch=payload.auto_dispatch or False,
    )
    return StandardResponse(
        data=result,
        message=f"Pipeline 4 processed inbound {payload.channel} message from {payload.sender}.",
    )


# -----------------------------------------------------------------------------
# 5. Human Approval & Dispatch Actions
# -----------------------------------------------------------------------------
@router.post("/conversations/{conversation_id}/approve", response_model=StandardResponse[Dict[str, Any]])
async def approve_and_send(
    conversation_id: str,
    payload: Optional[ApproveReplyPayload] = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Approve pending AI response draft and dispatch via Microsoft Outlook or SMS."""
    org_id = current_user.organization_id

    # Find pending approval item
    appr_res = await session.execute(
        select(ApprovalItem).where(
            ApprovalItem.organization_id == org_id,
            ApprovalItem.artifact_id == conversation_id,
            ApprovalItem.status == "pending",
        )
    )
    appr = appr_res.scalars().first()
    if not appr:
        raise HTTPException(status_code=404, detail="No pending draft approval found for this conversation")

    # Find conversation and contact
    conv_res = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_res.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    con_res = await session.execute(select(Contact).where(Contact.id == conv.contact_id))
    contact = con_res.scalars().first()
    target_addr = contact.email if conv.channel == "email" else (contact.phone if contact else "unknown")

    content_to_send = (payload.edited_content if payload and payload.edited_content else appr.draft_content).strip()

    # Dispatch message
    engine = Pipeline4Engine(session)
    dispatch_res = await engine.dispatch_reply(
        conversation_id=conversation_id,
        channel=conv.channel,
        recipient=target_addr,
        body=content_to_send,
        subject="Re: Following up on your inquiry",
    )

    appr.status = "sent"
    appr.draft_content = content_to_send
    appr.reviewed_by = current_user.id
    appr.review_feedback = "Approved by human representative."
    await session.commit()

    return StandardResponse(
        data=dispatch_res,
        message=f"Reply dispatched successfully via {conv.channel.upper()} to {target_addr}.",
    )


@router.post("/conversations/{conversation_id}/takeover", response_model=StandardResponse[Dict[str, Any]])
async def activate_human_takeover(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Activate human takeover on a conversation, pausing autonomous AI replies."""
    conv_res = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_res.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.is_human_takeover = True
    conv.status = "human_takeover"
    conv.assigned_user_id = current_user.id
    await session.commit()

    return StandardResponse(
        data={"conversation_id": conv.id, "is_human_takeover": True, "status": conv.status},
        message="Human takeover activated. Autonomous AI responses suspended.",
    )


@router.post("/conversations/{conversation_id}/resume", response_model=StandardResponse[Dict[str, Any]])
async def resume_autonomous_agent(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Resume autonomous AI responses for a conversation."""
    conv_res = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_res.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.is_human_takeover = False
    conv.status = "active"
    await session.commit()

    return StandardResponse(
        data={"conversation_id": conv.id, "is_human_takeover": False, "status": conv.status},
        message="Autonomous AI responses resumed for conversation.",
    )


# -----------------------------------------------------------------------------
# 6. Meeting Scheduling & Management Endpoints
# -----------------------------------------------------------------------------
@router.get("/meetings", response_model=StandardResponse[Dict[str, Any]])
async def list_meetings(
    status: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all meetings arranged by the 24/7 Lead Responder Agent."""
    org_id = current_user.organization_id

    stmt = select(MeetingBooking).where(MeetingBooking.organization_id == org_id).order_by(desc(MeetingBooking.created_at))
    res = await session.execute(stmt)
    bookings = res.scalars().all()

    items = []
    for b in bookings:
        if status and status.lower() != "all" and b.status.lower() != status.lower():
            continue
        items.append({
            "id": b.id,
            "conversation_id": b.conversation_id,
            "contact_id": b.contact_id,
            "attendee_name": b.attendee_name,
            "attendee_email": b.attendee_email,
            "organizer_email": b.organizer_email,
            "title": b.title,
            "start_time": b.start_time,
            "end_time": b.end_time,
            "timezone": b.timezone,
            "status": b.status,
            "teams_join_url": b.teams_join_url,
            "outlook_event_id": b.outlook_event_id,
            "auto_booked": b.auto_booked,
            "created_at": str(b.created_at),
        })

    # Fetch meeting proposals
    prop_stmt = select(MeetingProposal).where(MeetingProposal.organization_id == org_id).order_by(desc(MeetingProposal.created_at))
    prop_res = await session.execute(prop_stmt)
    proposals = [
        {
            "id": p.id,
            "contact_id": p.contact_id,
            "requested_slot": p.requested_slot,
            "offered_slots": p.offered_slots,
            "status": p.status,
            "expires_at": p.expires_at,
        }
        for p in prop_res.scalars().all()
    ]

    return StandardResponse(
        data={
            "bookings": items,
            "proposals": proposals,
        },
        message="Meetings loaded successfully",
    )


@router.post("/meetings/{booking_id}/cancel", response_model=StandardResponse[Dict[str, Any]])
async def cancel_meeting(
    booking_id: str,
    payload: Optional[CancelMeetingPayload] = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Cancel a confirmed Outlook calendar meeting."""
    stmt = select(MeetingBooking).where(MeetingBooking.id == booking_id)
    res = await session.execute(stmt)
    booking = res.scalars().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Meeting booking not found")

    engine = Pipeline4Engine(session)
    await engine.calendar_adapter.cancel_meeting(
        outlook_event_id=booking.outlook_event_id,
        reason=payload.reason if payload else "Cancelled by sales representative",
    )

    booking.status = "cancelled"
    booking.cancellation_reason = payload.reason if payload else "Cancelled"
    await session.commit()

    return StandardResponse(
        data={"booking_id": booking.id, "status": "cancelled"},
        message=f"Meeting '{booking.title}' cancelled successfully.",
    )


@router.post("/meetings/{booking_id}/reschedule", response_model=StandardResponse[Dict[str, Any]])
async def reschedule_meeting(
    booking_id: str,
    payload: RescheduleMeetingPayload,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Reschedule a confirmed Outlook calendar meeting."""
    stmt = select(MeetingBooking).where(MeetingBooking.id == booking_id)
    res = await session.execute(stmt)
    booking = res.scalars().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Meeting booking not found")

    engine = Pipeline4Engine(session)
    await engine.calendar_adapter.reschedule_meeting(
        outlook_event_id=booking.outlook_event_id,
        new_start_iso=payload.new_start_time,
        new_end_iso=payload.new_end_time,
        timezone_name=payload.timezone or "UTC",
    )

    booking.start_time = payload.new_start_time
    booking.end_time = payload.new_end_time
    booking.status = "booking_confirmed"
    await session.commit()

    return StandardResponse(
        data={"booking_id": booking.id, "status": "rescheduled", "new_start": payload.new_start_time},
        message=f"Meeting rescheduled to {payload.new_start_time}.",
    )


# -----------------------------------------------------------------------------
# 7. Workflow Telemetry & Monitoring (The 5 Nodes)
# -----------------------------------------------------------------------------
def _safe_json(val: Any) -> Any:
    if not val:
        return {}
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return {"raw": str(val)}


@router.get("/monitoring", response_model=StandardResponse[List[Dict[str, Any]]])
async def get_node_monitoring(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve 5-node Pipeline 4 telemetry logs and latency for workflow observability."""
    org_id = current_user.organization_id

    stmt = (
        select(NodeExecutionLog)
        .where(NodeExecutionLog.organization_id == org_id)
        .order_by(desc(NodeExecutionLog.created_at))
        .limit(limit)
    )
    res = await session.execute(stmt)
    logs = res.scalars().all()

    items = []
    for log_item in logs:
        items.append({
            "id": log_item.id,
            "message_id": log_item.message_id,
            "conversation_id": log_item.conversation_id,
            "channel": log_item.channel,
            "node1_ingest": _safe_json(log_item.node1_ingest),
            "node2_context": _safe_json(log_item.node2_context),
            "node3_safety": _safe_json(log_item.node3_safety),
            "node4_memory": _safe_json(log_item.node4_memory),
            "node5_intent_draft": _safe_json(log_item.node5_intent_draft),
            "approval_status": log_item.approval_status,
            "send_status": log_item.send_status,
            "total_latency_ms": log_item.total_latency_ms,
            "status": log_item.status,
            "timestamp": str(log_item.created_at),
        })

    return StandardResponse(data=items, message="Pipeline 4 node telemetry loaded")


# -----------------------------------------------------------------------------
# 8. Scenario Simulator (Testing all 5 Nodes End-to-End)
# -----------------------------------------------------------------------------
@router.post("/simulate", response_model=StandardResponse[Dict[str, Any]])
async def simulate_scenario(
    payload: SimulateScenarioPayload,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Test trigger to simulate production scenarios through the 5 nodes:
    - meeting_request_2am: Customer requests 2 AM -> 2 AM occupied -> 3 AM offered!
    - meeting_confirm_3am: Customer replies 'Yes, 3 AM works' -> 3 AM automatically booked with Teams link!
    - demo_request: Customer asks for demo -> P3 Demo retrieved!
    - stop_opt_out: Customer texts 'STOP' -> Hard suppression recorded!
    - general_question: Customer asks technical question -> Grounded Knowledge Base answer!
    """
    scenario = payload.scenario or payload.scenario_type or "2am_meeting_request"
    sender = (
        payload.sender
        or payload.sender_email
        or payload.sender_phone
        or ("alex.morgan@techflow.io" if payload.channel == "email" else "+15550199")
    )

    if payload.body:
        body = payload.body
    elif scenario in ("meeting_request_2am", "2am_meeting_request"):
        body = "Can we meet tomorrow at 2 AM? Our team needs to review integration details."
    elif scenario in ("meeting_confirm_3am", "lead_confirmation_3am"):
        body = "Yes, 3 AM works. Please send the meeting invitation."
    elif scenario in ("demo_request", "demo_video"):
        body = "Can you send me a demo video and walkthrough of your document extraction solution?"
    elif scenario in ("stop_opt_out", "opt_out_stop"):
        body = "STOP. Please unsubscribe me and remove me from all lists."
    elif scenario in ("negative_tone_interest", "negative_tone_buying_interest"):
        body = "Our current document operations system is terrible and slow. Can your AI help us automate extraction?"
    elif scenario in ("cancel_meeting", "human_handoff"):
        body = "Can I please speak directly with a human sales representative?"
    else:
        body = "Does your platform support bidirectional CRM synchronization with HubSpot and custom webhooks?"

    engine = Pipeline4Engine(session)
    result = await engine.process_inbound_message(
        sender=sender,
        recipient="sales@adople.ai",
        body=body,
        channel=payload.channel or "sms",
        provider="simulator",
        provider_message_id=f"sim-{uuid.uuid4().hex[:8]}",
        organization_id=current_user.organization_id,
        auto_dispatch=False,
    )

    response_data = {
        "simulation_scenario": scenario,
        "sender": sender,
        "body": body,
        "channel": payload.channel or "sms",
        "result": result,
        **result,
    }

    return StandardResponse(
        data=response_data,
        message=f"Simulation of scenario '{scenario}' completed.",
    )
