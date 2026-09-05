import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.database import get_db
from app.models import FormatTier, GraphEdge, Module, ModuleStatus, Topic, TopicStatus
from app.schemas import (
    BudgetContinueRequest,
    IntakeQuestionsRequest,
    IntakeQuestionsResponse,
    ModuleSummary,
    OutlineApproveRequest,
    TopicCreate,
    TopicDetail,
    TopicListItem,
    TopicMoveRequest,
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


def _module_summary(module: Module) -> ModuleSummary:
    quiz_score = None
    if module.quiz_last_result_json:
        quiz_score = json.loads(module.quiz_last_result_json).get("weighted_score")
    scored_sessions = [s.score for s in module.sessions if s.score is not None]
    return ModuleSummary(
        id=module.id,
        order_index=module.order_index,
        title=module.title,
        one_liner=module.one_liner,
        status=module.status,
        unlocked=research.is_module_unlocked(module),
        has_quiz=module.quiz_json is not None,
        quiz_passed=module.quiz_passed,
        quiz_score=quiz_score,
        sessions_count=len(module.sessions),
        best_session_score=max(scored_sessions, default=None),
    )


def _topic_detail(db: Session, topic: Topic) -> TopicDetail:
    b = budget.get_or_create(db, topic.id)
    current_module = (
        db.query(Module)
        .filter(Module.topic_id == topic.id, Module.status != ModuleStatus.completed)
        .order_by(Module.order_index)
        .first()
    )
    cap_hit = b.call_count >= b.soft_cap * (1 + b.cap_acknowledgments)
    modules_total = len(topic.modules)
    modules_researched = sum(1 for m in topic.modules if m.digest_path is not None)
    return TopicDetail(
        id=topic.id,
        title=topic.title,
        format_tier=topic.format_tier,
        depth=topic.depth,
        status=topic.status,
        program_id=topic.program_id,
        created_at=topic.created_at,
        completed_at=topic.completed_at,
        digest_path=topic.digest_path,
        outline_approved=topic.outline_approved,
        current_module_id=current_module.id if current_module else None,
        modules=[_module_summary(m) for m in topic.modules],
        modules_total=modules_total,
        modules_researched=modules_researched,
        research_in_progress=(
            modules_total > 0 and modules_researched < modules_total and not cap_hit and not topic.research_error
        ),
        research_error=topic.research_error,
        budget_used=b.call_count,
        budget_soft_cap=b.soft_cap,
        budget_cap_hit=cap_hit,
    )


@router.post("/intake-questions", response_model=IntakeQuestionsResponse)
def get_intake_questions(payload: IntakeQuestionsRequest):
    questions = research.generate_intake_questions(payload.title, payload.format_tier)
    return IntakeQuestionsResponse(questions=questions)


@router.post("", response_model=TopicDetail)
def create_topic(payload: TopicCreate, db: Session = Depends(get_db)):
    topic = Topic(
        title=payload.title,
        format_tier=payload.format_tier,
        depth=payload.depth,
        program_id=payload.program_id,
        learner_context=payload.learner_context,
        status=TopicStatus.planning,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    budget.get_or_create(db, topic.id)

    try:
        research.kickoff(db, topic)
    except budget.BudgetExceeded as e:
        raise _budget_error(e)
    except Exception as e:
        # Nothing usable was produced (no digest, no modules) — don't leave a dead
        # "planning" topic behind with no explanation and no way to retry.
        db.delete(topic)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Research failed, so this topic wasn't created: {e}")

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


@router.post("/{topic_id}/move", response_model=TopicDetail)
def move_topic(topic_id: int, payload: TopicMoveRequest, db: Session = Depends(get_db)):
    from app.models import Program

    topic = _get_topic_or_404(db, topic_id)
    if payload.program_id is not None and db.get(Program, payload.program_id) is None:
        raise HTTPException(status_code=404, detail="Program not found")
    topic.program_id = payload.program_id
    db.commit()
    db.refresh(topic)
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
def approve_outline(
    topic_id: int, payload: OutlineApproveRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
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

    research.approve_outline(db, topic, modules_override)
    # Researching every module can take minutes for a full course — runs after this response
    # goes out. Poll GET /topics/{id} for modules_researched / modules_total to show progress.
    background_tasks.add_task(research.research_all_modules_background, topic.id)

    db.refresh(topic)
    return _topic_detail(db, topic)


@router.post("/{topic_id}/budget/continue", response_model=TopicDetail)
def continue_past_budget(
    topic_id: int, payload: BudgetContinueRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    topic = _get_topic_or_404(db, topic_id)
    if not payload.continue_anyway:
        raise HTTPException(status_code=400, detail="continue_anyway must be true to proceed")

    budget.acknowledge_and_continue(db, topic_id)

    has_pending_modules = topic.outline_approved and any(m.digest_path is None for m in topic.modules)
    if has_pending_modules:
        background_tasks.add_task(research.research_all_modules_background, topic.id)
    else:
        try:
            research.resume_pending_research(db, topic)
        except budget.BudgetExceeded as e:
            raise _budget_error(e)
        except Exception as e:
            # Unlike a fresh create, this topic may already have real progress — record the
            # error instead of deleting anything, same as the background course-research path.
            topic.research_error = str(e)[:2000]
            db.commit()
            raise HTTPException(status_code=502, detail=f"Research failed: {e}")

    db.refresh(topic)
    return _topic_detail(db, topic)


@router.delete("/{topic_id}", status_code=204)
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = _get_topic_or_404(db, topic_id)

    digest_paths = {topic.digest_path} | {m.digest_path for m in topic.modules}
    digest_paths.discard(None)

    db.query(GraphEdge).filter((GraphEdge.topic_id_a == topic_id) | (GraphEdge.topic_id_b == topic_id)).delete(
        synchronize_session=False
    )
    db.delete(topic)  # cascades to modules -> sessions -> session_messages, and to budget_tracking
    db.commit()

    for rel_path in digest_paths:
        path = DATA_DIR / rel_path
        path.unlink(missing_ok=True)


@router.get("/{topic_id}/connections")
def get_topic_connections(topic_id: int, db: Session = Depends(get_db)):
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
