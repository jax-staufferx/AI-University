import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FormatTier, Module, ModuleStatus, Topic, TopicStatus
from app.schemas import (
    BudgetContinueRequest,
    ModuleSummary,
    OutlineApproveRequest,
    TopicCreate,
    TopicDetail,
    TopicListItem,
)
from app.services import budget, research

router = APIRouter(prefix="/topics", tags=["topics"])


def _get_topic_or_404(db: Session, topic_id: int) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def _budget_error(e: budget.BudgetExceeded) -> HTTPException:
    return HTTPException(
        status_code=402,
        detail={
            "message": str(e),
            "topic_id": e.topic_id,
            "call_count": e.call_count,
            "soft_cap": e.soft_cap,
            "continue_endpoint": f"/topics/{e.topic_id}/budget/continue",
        },
    )


def _topic_detail(db: Session, topic: Topic) -> TopicDetail:
    b = budget.get_or_create(db, topic.id)
    current_module = (
        db.query(Module)
        .filter(Module.topic_id == topic.id, Module.status != ModuleStatus.completed)
        .order_by(Module.order_index)
        .first()
    )
    return TopicDetail(
        id=topic.id,
        title=topic.title,
        format_tier=topic.format_tier,
        status=topic.status,
        created_at=topic.created_at,
        completed_at=topic.completed_at,
        digest_path=topic.digest_path,
        outline_approved=topic.outline_approved,
        current_module_id=current_module.id if current_module else None,
        modules=[ModuleSummary.model_validate(m) for m in topic.modules],
        budget_used=b.call_count,
        budget_soft_cap=b.soft_cap,
        budget_cap_hit=b.call_count >= b.soft_cap * (1 + b.cap_acknowledgments),
    )


@router.post("", response_model=TopicDetail)
def create_topic(payload: TopicCreate, db: Session = Depends(get_db)):
    topic = Topic(title=payload.title, format_tier=payload.format_tier, status=TopicStatus.planning)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    budget.get_or_create(db, topic.id)

    try:
        research.kickoff(db, topic)
    except budget.BudgetExceeded as e:
        raise _budget_error(e)

    db.refresh(topic)
    return _topic_detail(db, topic)


@router.get("", response_model=list[TopicListItem])
def list_topics(db: Session = Depends(get_db)):
    topics = db.query(Topic).order_by(Topic.created_at.desc()).all()
    return [TopicListItem.model_validate(t) for t in topics]


@router.get("/{topic_id}", response_model=TopicDetail)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = _get_topic_or_404(db, topic_id)
    return _topic_detail(db, topic)


@router.get("/{topic_id}/outline")
def get_proposed_outline(topic_id: int, db: Session = Depends(get_db)):
    topic = _get_topic_or_404(db, topic_id)
    if topic.format_tier not in (FormatTier.short_course, FormatTier.full_course):
        raise HTTPException(status_code=400, detail="Only short_course/full_course topics have an outline")
    if not topic.outline_json:
        raise HTTPException(status_code=409, detail="Outline not generated yet")
    return {"modules": json.loads(topic.outline_json), "approved": topic.outline_approved}


@router.post("/{topic_id}/outline/approve", response_model=TopicDetail)
def approve_outline(topic_id: int, payload: OutlineApproveRequest, db: Session = Depends(get_db)):
    topic = _get_topic_or_404(db, topic_id)
    if topic.format_tier not in (FormatTier.short_course, FormatTier.full_course):
        raise HTTPException(status_code=400, detail="Only short_course/full_course topics have an outline")
    if topic.outline_approved:
        raise HTTPException(status_code=409, detail="Outline already approved")
    if not topic.outline_json:
        raise HTTPException(status_code=409, detail="Outline not generated yet")

    modules_override = None
    if payload.modules is not None:
        modules_override = [
            {
                "title": m.title,
                "one_liner": m.one_liner,
                "content_type": m.content_type.value,
            }
            for m in sorted(payload.modules, key=lambda m: m.order_index)
        ]

    try:
        research.approve_outline(db, topic, modules_override)
    except budget.BudgetExceeded as e:
        raise _budget_error(e)

    db.refresh(topic)
    return _topic_detail(db, topic)


@router.post("/{topic_id}/budget/continue", response_model=TopicDetail)
def continue_past_budget(topic_id: int, payload: BudgetContinueRequest, db: Session = Depends(get_db)):
    topic = _get_topic_or_404(db, topic_id)
    if not payload.continue_anyway:
        raise HTTPException(status_code=400, detail="continue_anyway must be true to proceed")

    budget.acknowledge_and_continue(db, topic_id)
    try:
        research.resume_pending_research(db, topic)
    except budget.BudgetExceeded as e:
        raise _budget_error(e)

    db.refresh(topic)
    return _topic_detail(db, topic)


@router.get("/{topic_id}/connections")
def get_topic_connections(topic_id: int, db: Session = Depends(get_db)):
    from app.models import GraphEdge

    _get_topic_or_404(db, topic_id)
    edges = (
        db.query(GraphEdge)
        .filter((GraphEdge.topic_id_a == topic_id) | (GraphEdge.topic_id_b == topic_id))
        .all()
    )
    out = []
    for e in edges:
        other_id = e.topic_id_b if e.topic_id_a == topic_id else e.topic_id_a
        other = db.get(Topic, other_id)
        out.append(
            {
                "topic_id": other_id,
                "topic_title": other.title if other else None,
                "connection_note": e.connection_note,
            }
        )
    return out
