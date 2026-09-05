from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.database import get_db
from app.models import Module, Topic
from app.schemas import ModuleDetail, QuizOut, QuizSubmitRequest, QuizSubmitResult, SessionSummary, SlideshowOut
from app.services import budget, quiz, slideshow
from app.services.research import is_module_unlocked, read_digest

router = APIRouter(prefix="/topics", tags=["modules"])


def _module_or_404(db: Session, topic_id: int, module_id: int) -> Module:
    module = db.get(Module, module_id)
    if module is None or module.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


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


@router.get("/{topic_id}/modules/{module_id}", response_model=ModuleDetail)
def get_module(topic_id: int, module_id: int, db: Session = Depends(get_db)):
    module = _module_or_404(db, topic_id, module_id)
    unlocked = is_module_unlocked(module)

    return ModuleDetail(
        id=module.id,
        topic_id=module.topic_id,
        order_index=module.order_index,
        title=module.title,
        one_liner=module.one_liner,
        content_type=module.content_type,
        status=module.status,
        unlocked=unlocked,
        digest_path=module.digest_path,
        # Withhold content for locked modules even though it may already be sitting in the
        # DB (pre-fetched) — the point of locking is what the learner can see, not just do.
        digest_markdown=read_digest(module.digest_path) if unlocked else None,
        quiz_passed=module.quiz_passed,
        has_quiz=module.quiz_json is not None,
        has_slideshow=module.slideshow_json is not None,
        sessions=[SessionSummary.model_validate(s) for s in module.sessions],
    )


@router.delete("/{topic_id}/modules/{module_id}", status_code=204)
def delete_module(topic_id: int, module_id: int, db: Session = Depends(get_db)):
    module = _module_or_404(db, topic_id, module_id)
    digest_path = module.digest_path

    db.delete(module)  # cascades to sessions -> session_messages
    db.commit()

    if digest_path:
        topic = db.get(Topic, topic_id)
        still_referenced = (topic is not None and topic.digest_path == digest_path) or any(
            m.digest_path == digest_path for m in (topic.modules if topic else [])
        )
        if not still_referenced:
            (DATA_DIR / digest_path).unlink(missing_ok=True)


@router.get("/{topic_id}/modules/{module_id}/quiz", response_model=QuizOut)
def get_quiz(topic_id: int, module_id: int, db: Session = Depends(get_db)):
    module = _module_or_404(db, topic_id, module_id)
    if not is_module_unlocked(module):
        raise HTTPException(status_code=409, detail="Complete earlier modules first")
    if not module.quiz_json:
        raise HTTPException(status_code=409, detail="Quiz not generated yet for this module")
    return quiz.get_quiz_for_frontend(module)


@router.get("/{topic_id}/modules/{module_id}/quiz/result", response_model=QuizSubmitResult)
def get_quiz_result(topic_id: int, module_id: int, db: Session = Depends(get_db)):
    module = _module_or_404(db, topic_id, module_id)
    result = quiz.get_last_quiz_result(module)
    if result is None:
        raise HTTPException(status_code=404, detail="No quiz attempt yet for this module")
    return result


@router.post("/{topic_id}/modules/{module_id}/quiz/submit", response_model=QuizSubmitResult)
def submit_quiz(topic_id: int, module_id: int, payload: QuizSubmitRequest, db: Session = Depends(get_db)):
    module = _module_or_404(db, topic_id, module_id)
    if not is_module_unlocked(module):
        raise HTTPException(status_code=409, detail="Complete earlier modules first")
    if not module.quiz_json:
        raise HTTPException(status_code=409, detail="Quiz not generated yet for this module")

    try:
        result = quiz.grade_quiz(db, module, payload.answers)
    except budget.BudgetExceeded as e:
        raise _budget_error(e)

    if result.passed and not module.slideshow_json:
        try:
            slideshow.generate_slideshow(db, module, result)
        except budget.BudgetExceeded:
            pass  # quiz result still stands; slideshow can be generated on next GET attempt

    return result


@router.get("/{topic_id}/modules/{module_id}/slideshow", response_model=SlideshowOut)
def get_slideshow(topic_id: int, module_id: int, db: Session = Depends(get_db)):
    module = _module_or_404(db, topic_id, module_id)
    if not is_module_unlocked(module):
        raise HTTPException(status_code=409, detail="Complete earlier modules first")
    if not module.quiz_passed:
        raise HTTPException(status_code=409, detail="Pass the quiz first to unlock the lesson")
    if not module.slideshow_json:
        raise HTTPException(status_code=409, detail="Lesson not generated yet — try resubmitting the quiz")
    return slideshow.get_slideshow_for_frontend(module)
