"""Soft-cap tracking for research/API calls, per topic.

On hitting the cap the caller must surface a warning to the user and let them explicitly
opt to keep going (BudgetExceeded) — each "continue anyway" buys one more soft_cap's worth
of calls rather than disabling the check forever.
"""

from sqlalchemy.orm import Session

from app.config import settings
from app.models import BudgetTracking


class BudgetExceeded(Exception):
    def __init__(self, topic_id: int, call_count: int, soft_cap: int):
        self.topic_id = topic_id
        self.call_count = call_count
        self.soft_cap = soft_cap
        super().__init__(
            f"Research soft cap ({soft_cap} calls) reached for topic {topic_id} "
            f"({call_count} calls made). User must confirm to continue."
        )


def get_or_create(db: Session, topic_id: int) -> BudgetTracking:
    budget = db.query(BudgetTracking).filter_by(topic_id=topic_id).one_or_none()
    if budget is None:
        budget = BudgetTracking(topic_id=topic_id, call_count=0, soft_cap=settings.research_call_soft_cap)
        db.add(budget)
        db.commit()
        db.refresh(budget)
    return budget


def _allowed_calls(budget: BudgetTracking) -> int:
    return budget.soft_cap * (1 + budget.cap_acknowledgments)


def check_and_increment(db: Session, topic_id: int, n: int = 1) -> BudgetTracking:
    budget = get_or_create(db, topic_id)
    if budget.call_count >= _allowed_calls(budget):
        raise BudgetExceeded(topic_id, budget.call_count, budget.soft_cap)
    budget.call_count += n
    db.commit()
    db.refresh(budget)
    return budget


def acknowledge_and_continue(db: Session, topic_id: int) -> BudgetTracking:
    budget = get_or_create(db, topic_id)
    budget.cap_acknowledgments += 1
    db.commit()
    db.refresh(budget)
    return budget
