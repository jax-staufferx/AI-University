"""The monitor agent. Runs quietly: logs every session's outcome into the learner profile,
and once there's enough data, proposes concrete weighting changes — never applies them
without explicit user confirmation."""

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ContentType, LearnerProfile, LearningMethod, MonitorProposal, ProposalStatus
from app.services.methods import method_label

PATTERN_MIN_TOTAL_SESSIONS = 5  # one bad session isn't a learning-style diagnosis
PATTERN_MIN_METHOD_SESSIONS = 3  # per-method sample size before its average means anything
DEVIATION_THRESHOLD = 15.0  # points off the content-type's average before it's "worth acting on"
WEIGHT_UP = 1.3
WEIGHT_DOWN = 0.7
WEIGHT_MIN = 0.3
WEIGHT_MAX = 3.0


def log_session(db: Session, content_type: ContentType, method: LearningMethod, score: int) -> None:
    profile = (
        db.query(LearnerProfile).filter_by(content_type=content_type, method=method).one_or_none()
    )
    if profile is None:
        profile = LearnerProfile(content_type=content_type, method=method, sessions_count=0, score_sum=0, weight=1.0)
        db.add(profile)
    profile.sessions_count += 1
    profile.score_sum += score
    db.commit()
    _maybe_propose(db, content_type)


def _maybe_propose(db: Session, content_type: ContentType) -> None:
    total = db.query(func.sum(LearnerProfile.sessions_count)).scalar() or 0
    if total < PATTERN_MIN_TOTAL_SESSIONS:
        return

    profiles = db.query(LearnerProfile).filter_by(content_type=content_type).all()
    eligible = [p for p in profiles if p.sessions_count >= PATTERN_MIN_METHOD_SESSIONS]
    if len(eligible) < 2:
        return  # nothing to compare against yet

    overall_avg = sum(p.avg_score for p in eligible) / len(eligible)

    for p in eligible:
        deviation = p.avg_score - overall_avg
        if abs(deviation) < DEVIATION_THRESHOLD:
            continue

        existing = (
            db.query(MonitorProposal)
            .filter_by(content_type=content_type, method=p.method, status=ProposalStatus.pending)
            .one_or_none()
        )
        if existing is not None:
            continue

        proposed_weight = round(
            min(WEIGHT_MAX, p.weight * WEIGHT_UP) if deviation > 0 else max(WEIGHT_MIN, p.weight * WEIGHT_DOWN),
            2,
        )
        if abs(proposed_weight - p.weight) < 0.05:
            continue

        direction = "outperforms" if deviation > 0 else "underperforms"
        rationale = (
            f"Across {p.sessions_count} {method_label(p.method)} sessions on {content_type.value} "
            f"topics, average score is {p.avg_score:.0f} vs {overall_avg:.0f} average across "
            f"methods tried on this content type — {direction} the average by {abs(deviation):.0f} "
            f"points. Proposing weight {p.weight:.2f} -> {proposed_weight:.2f}."
        )
        db.add(
            MonitorProposal(
                content_type=content_type,
                method=p.method,
                current_weight=p.weight,
                proposed_weight=proposed_weight,
                rationale=rationale,
                status=ProposalStatus.pending,
            )
        )
    db.commit()


def respond_to_proposal(db: Session, proposal: MonitorProposal, approve: bool) -> MonitorProposal:
    proposal.status = ProposalStatus.approved if approve else ProposalStatus.rejected
    proposal.responded_at = datetime.now(timezone.utc)
    if approve:
        profile = (
            db.query(LearnerProfile)
            .filter_by(content_type=proposal.content_type, method=proposal.method)
            .one_or_none()
        )
        if profile is not None:
            profile.weight = proposal.proposed_weight
    db.commit()
    db.refresh(proposal)
    return proposal
