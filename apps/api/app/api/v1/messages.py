"""Messages endpoints — list by conversation + send.

Agency-scoped via the messages table RLS (``agency_id`` column).
Composite FK ``(conversation_id, agency_id)`` prevents inserting a message
that points to another agency's conversation.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id, get_current_user, require_role
from ...models import Conversation, Message, User
from ...schemas import MessageCreate, MessageOut, PaginatedResponse
from ...services.audit import write_audit

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get("", response_model=PaginatedResponse[MessageOut])
def list_messages(
    conversation_id: uuid.UUID = Query(...),
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List messages in a conversation (oldest first by default — caller paginates forward)."""
    # Verify the conversation exists in the current agency
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.agency_id == agency_id,
        )
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    stmt = select(Message).where(
        Message.conversation_id == conversation_id,
        Message.agency_id == agency_id,
    )
    count_stmt = (
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id, Message.agency_id == agency_id)
    )
    # Hide internal notes from viewers? Phase 1: all agency members see them.
    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Message.created_at.asc()).limit(limit).offset(offset)
        ).all()
    )
    return PaginatedResponse[MessageOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    payload: MessageCreate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager", "agent")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == payload.conversation_id,
            Conversation.agency_id == agency_id,
        )
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if payload.reply_to_message_id is not None:
        parent = db.scalar(
            select(Message).where(
                Message.id == payload.reply_to_message_id,
                Message.conversation_id == payload.conversation_id,
                Message.agency_id == agency_id,
            )
        )
        if parent is None:
            raise HTTPException(status_code=400, detail="Reply-to message not found in this conversation")
    msg = Message(
        conversation_id=payload.conversation_id,
        agency_id=agency_id,
        sender_type="agent",
        sender_user_id=user.id,
        content=payload.content,
        is_internal=payload.is_internal,
        reply_to_message_id=payload.reply_to_message_id,
        delivery_status="sent",
    )
    db.add(msg)
    db.flush()
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="message.send",
        target_type="message",
        target_id=msg.id,
        metadata={
            "conversation_id": str(payload.conversation_id),
            "is_internal": payload.is_internal,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(msg)
    return msg
