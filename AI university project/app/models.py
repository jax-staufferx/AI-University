import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class FormatTier(str, enum.Enum):
    quick_dive = "quick_dive"
    deep_dive = "deep_dive"
    short_course = "short_course"
    full_course = "full_course"


class ContentDepth(str, enum.Enum):
    """How technical the research content, quiz, and lesson should be. Chosen by the learner
    at topic creation — distinct from the per-question 1-10 difficulty tags used internally
    for quiz scoring and slideshow weighting, which are diagnostic, not a user setting."""

    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class TopicStatus(str, enum.Enum):
    planning = "planning"
    active = "active"
    completed = "completed"


class ModuleStatus(str, enum.Enum):
    pending = "pending"
    researched = "researched"
    in_progress = "in_progress"
    completed = "completed"


class ContentType(str, enum.Enum):
    skill = "skill"
    conceptual = "conceptual"
    mixed = "mixed"


class LearningMethod(str, enum.Enum):
    teach_it_back = "teach_it_back"
    sparring = "sparring"
    ship_it = "ship_it"
    analogy_builder = "analogy_builder"
    error_hunt = "error_hunt"
    eli5 = "eli5"
    scenario_application = "scenario_application"
    rapid_recall = "rapid_recall"


class ProposalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Program(Base):
    """An optional folder grouping several topics together — e.g. a self-built degree-style
    curriculum spanning multiple courses. Purely local/organizational for now."""

    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    topics: Mapped[list["Topic"]] = relationship("Topic", back_populates="program")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    format_tier: Mapped[FormatTier] = mapped_column(Enum(FormatTier))
    depth: Mapped[ContentDepth] = mapped_column(Enum(ContentDepth), default=ContentDepth.intermediate)
    # Free-text answers from the pre-research intake questionnaire (why they're learning this,
    # what to focus on/skip, plus 1-2 AI-generated topic-specific questions) — woven into every
    # research/outline/quiz prompt alongside depth, so scope reflects intent, not just detail level.
    learner_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TopicStatus] = mapped_column(Enum(TopicStatus), default=TopicStatus.planning)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True)
    program: Mapped["Program | None"] = relationship("Program", back_populates="topics")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Quick/Deep Dive single-digest path (modules unused for these tiers)
    digest_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Short/Full Course curriculum brain state
    outline_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    outline_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    running_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when the background module-research task hits an error it can't recover from
    # (anything other than the budget cap, which has its own dedicated flow). Cleared on
    # the next successful research step so it doesn't linger after the real problem is fixed.
    research_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    modules: Mapped[list["Module"]] = relationship(
        "Module", back_populates="topic", cascade="all, delete-orphan", order_by="Module.order_index"
    )
    budget: Mapped["BudgetTracking | None"] = relationship(
        "BudgetTracking", back_populates="topic", uselist=False, cascade="all, delete-orphan"
    )


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    one_liner: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType), default=ContentType.mixed)
    status: Mapped[ModuleStatus] = mapped_column(Enum(ModuleStatus), default=ModuleStatus.pending)
    digest_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    researched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Diagnostic quiz gate: generated alongside the digest, must be passed before
    # active-recall sessions (the 8 methods) unlock for this module.
    quiz_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    quiz_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Full result (score, per-question right/wrong, explanations) from the most recent grading
    # pass, kept around so the learner can come back and review it later instead of it being
    # gone the moment they navigate away from the submit response.
    quiz_last_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Adaptive lesson generated only after the quiz is passed, weighted toward
    # whatever the quiz showed the learner is shakiest on.
    slideshow_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    topic: Mapped["Topic"] = relationship("Topic", back_populates="modules")
    sessions: Mapped[list["LearningSession"]] = relationship(
        "LearningSession", back_populates="module", cascade="all, delete-orphan"
    )


class LearningSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"))
    method_used: Mapped[LearningMethod] = mapped_column(Enum(LearningMethod))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 0-100 score assigned at grading time, used by the monitor agent
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    module: Mapped["Module"] = relationship("Module", back_populates="sessions")
    messages: Mapped[list["SessionMessage"]] = relationship(
        "SessionMessage", back_populates="session", cascade="all, delete-orphan", order_by="SessionMessage.id"
    )


class SessionMessage(Base):
    """Turn-by-turn transcript for interactive methods (sparring, teach-it-back, error hunt, ...)."""

    __tablename__ = "session_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    role: Mapped[str] = mapped_column(String(20))  # "agent" | "user"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    session: Mapped["LearningSession"] = relationship("LearningSession", back_populates="messages")


class LearnerProfile(Base):
    """Aggregated method-performance-by-topic-type record. Append-and-aggregate, never overwrite blindly."""

    __tablename__ = "learner_profile"
    __table_args__ = (UniqueConstraint("content_type", "method", name="uq_learner_profile_type_method"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType))
    method: Mapped[LearningMethod] = mapped_column(Enum(LearningMethod))
    sessions_count: Mapped[int] = mapped_column(Integer, default=0)
    score_sum: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    @property
    def avg_score(self) -> float | None:
        if self.sessions_count == 0:
            return None
        return self.score_sum / self.sessions_count


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id_a: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    topic_id_b: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    connection_note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class BudgetTracking(Base):
    __tablename__ = "budget_tracking"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), unique=True)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    soft_cap: Mapped[int] = mapped_column(Integer)
    # Each explicit "continue anyway" from the user buys one more soft_cap's worth of calls
    cap_acknowledgments: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    topic: Mapped["Topic"] = relationship("Topic", back_populates="budget")


class MonitorProposal(Base):
    __tablename__ = "monitor_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType))
    method: Mapped[LearningMethod] = mapped_column(Enum(LearningMethod))
    current_weight: Mapped[float] = mapped_column()
    proposed_weight: Mapped[float] = mapped_column()
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[ProposalStatus] = mapped_column(Enum(ProposalStatus), default=ProposalStatus.pending)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
