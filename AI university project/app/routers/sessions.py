from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LearningSession, Module, ModuleStatus, SessionMessage, Topic, TopicStatus
from app.schemas import SessionCreate, SessionDetail, SessionSubmitRequest, SessionSubmitResult
from app.services import budget, grading, knowledge_graph, methods, monitor_agent, research

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _session_or_404(db: Session, session_id: int) -> LearningSession:
    session = db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _session_detail(session: LearningSession) -> SessionDetail:
    return SessionDetail(
        id=session.id,
        module_id=session.module_id,
        method_used=session.method_used,
        started_at=session.started_at,
        completed_at=session.completed_at,
        score=session.score,
        outcome_summary=session.outcome_summary,
        messages=[
            {"role": m.role, "content": m.content, "created_at": m.created_at} for m in session.messages
        ],
    )


@router.post("", response_model=SessionDetail)
def start_session(payload: SessionCreate, db: Session = Depends(get_db)):
    module = db.get(Module, payload.module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found")
    if module.status == ModuleStatus.pending:
        raise HTTPException(status_code=409, detail="Module hasn't been researched yet")

    method = payload.method or methods.select_method(db, module)
    if module.status == ModuleStatus.researched:
        module.status = ModuleStatus.in_progress

    session = LearningSession(module_id=module.id, method_used=method)
    db.add(session)
    db.flush()

    opening = methods.opening_prompt(module, method)
    db.add(SessionMessage(session_id=session.id, role="agent", content=opening))
    db.commit()
    db.refresh(session)
    return _session_detail(session)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: Session = Depends(get_db)):
    return _session_detail(_session_or_404(db, session_id))


@router.post("/{session_id}/submit", response_model=SessionSubmitResult)
def submit_response(session_id: int, payload: SessionSubmitRequest, db: Session = Depends(get_db)):
    session = _session_or_404(db, session_id)
    if session.completed_at is not None:
        raise HTTPException(status_code=409, detail="Session already completed")

    module = db.get(Module, session.module_id)
    topic = db.get(Topic, module.topic_id)

    db.add(SessionMessage(session_id=session.id, role="user", content=payload.response))
    db.commit()
    db.refresh(session)

    transcript = [(m.role, m.content) for m in session.messages]
    user_turns = sum(1 for m in session.messages if m.role == "user")
    method = session.method_used

    if method in methods.INTERACTIVE_METHODS and user_turns < methods.MAX_INTERACTIVE_ROUNDS:
        followup = methods.followup_prompt(module, method, transcript)
        db.add(SessionMessage(session_id=session.id, role="agent", content=followup))
        db.commit()
        return SessionSubmitResult(session_id=session.id, completed=False, feedback="", next_prompt=followup)

    score, feedback = grading.grade_session(module, method, transcript, payload.response)
    session.completed_at = datetime.now(timezone.utc)
    session.score = score
    session.outcome_summary = feedback[:500]
    session.result = payload.response
    db.commit()

    if module.status != ModuleStatus.completed:
        module.status = ModuleStatus.completed
        module.completed_at = session.completed_at
        db.commit()

    monitor_agent.log_session(db, module.content_type, method, score)

    try:
        research.advance_after_module_completion(db, topic, module)
    except budget.BudgetExceeded:
        pass  # next module's pre-fetch is paused; user can resume via /topics/{id}/budget/continue

    db.refresh(topic)
    if topic.status == TopicStatus.completed:
        try:
            knowledge_graph.check_topic_overlap(db, topic)
        except budget.BudgetExceeded:
            pass  # non-critical; skip if the topic's budget is exhausted

    return SessionSubmitResult(session_id=session.id, completed=True, feedback=feedback, score=score)
