"""
routes/tickets.py — FastAPI route handlers for the /tickets endpoints.

Endpoints
---------
POST /tickets
    Body  : { "text": str, "user_id": str }
    Action: classify → generate response → persist → return result

GET  /tickets/escalated
    Returns all tickets with status "needs_human_review"

GET  /tickets
    Returns all tickets (useful for debugging / admin)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import database
from classifier import classify_ticket
from response_handler import generate_response

router = APIRouter(prefix="/tickets", tags=["tickets"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TicketRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    user_id: str = Field(..., min_length=1, max_length=128)


class ClassificationResult(BaseModel):
    intent: str
    confidence: float
    entities: dict


class TicketResponse(BaseModel):
    id: str
    text: str
    user_id: str
    classification: ClassificationResult
    response: str | None
    status: str
    created_at: str


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post("", response_model=TicketResponse, status_code=201)
async def submit_ticket(payload: TicketRequest):
    """
    Classify a new support ticket and generate an automated response.
    """
    ticket_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # 1. Classify
    classification = classify_ticket(payload.text)

    # 2. Generate response
    response_text, status = generate_response(
        intent=classification["intent"],
        user_id=payload.user_id,
        entities=classification.get("entities", {}),
    )

    # 3. Persist
    database.insert_ticket(
        id=ticket_id,
        text=payload.text,
        intent=classification["intent"],
        confidence=classification["confidence"],
        entities=classification.get("entities", {}),
        response=response_text,
        status=status,
        created_at=created_at,
    )

    return TicketResponse(
        id=ticket_id,
        text=payload.text,
        user_id=payload.user_id,
        classification=ClassificationResult(**classification),
        response=response_text,
        status=status,
        created_at=created_at,
    )


@router.get("/escalated")
async def get_escalated():
    """
    Return all tickets flagged for human review (status = needs_human_review).
    """
    tickets = database.get_escalated_tickets()
    return {"tickets": tickets, "count": len(tickets)}


@router.get("")
async def list_tickets():
    """Return all tickets (admin / debug view)."""
    tickets = database.get_all_tickets()
    return {"tickets": tickets, "count": len(tickets)}
