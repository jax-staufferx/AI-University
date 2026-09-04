from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import ContentDepth, ContentType, FormatTier, LearningMethod, ModuleStatus, ProposalStatus, TopicStatus

# ---------------------------------------------------------------------------
# Programs (optional folders grouping several topics)
# ---------------------------------------------------------------------------


class ProgramCreate(BaseModel):
    title: str
    description: str | None = None


class ProgramListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    created_at: datetime
    topic_count: int = 0


class ProgramDetail(ProgramListItem):
    topics: list["TopicListItem"] = []


class TopicMoveRequest(BaseModel):
    program_id: int | None  # null to remove from its program


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


class TopicCreate(BaseModel):
    title: str
    format_tier: FormatTier
    depth: ContentDepth = ContentDepth.intermediate
    program_id: int | None = None


class TopicListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    format_tier: FormatTier
    depth: ContentDepth
    status: TopicStatus
    program_id: int | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ModuleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    title: str
    one_liner: str | None = None
    status: ModuleStatus


class TopicDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    format_tier: FormatTier
    depth: ContentDepth
    status: TopicStatus
    program_id: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
    digest_path: str | None = None
    outline_approved: bool
    current_module_id: int | None = None
    modules: list[ModuleSummary] = []
    # For course tiers: every module is researched upfront, in the background, right after
    # outline approval. Poll this endpoint and watch these two climb together for a progress bar.
    modules_total: int = 0
    modules_researched: int = 0
    research_in_progress: bool = False
    research_error: str | None = None
    budget_used: int = 0
    budget_soft_cap: int = 0
    budget_cap_hit: bool = False


class OutlineModuleEdit(BaseModel):
    order_index: int
    title: str
    one_liner: str | None = None
    content_type: ContentType = ContentType.mixed


class OutlineApproveRequest(BaseModel):
    # If omitted, approves the proposed outline as-is. Pass modules to override/edit before approval.
    modules: list[OutlineModuleEdit] | None = None


class BudgetContinueRequest(BaseModel):
    continue_anyway: bool = True


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------


class ModuleDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    order_index: int
    title: str
    one_liner: str | None = None
    content_type: ContentType
    status: ModuleStatus
    unlocked: bool = True
    digest_path: str | None = None
    digest_markdown: str | None = None
    quiz_passed: bool = False
    has_quiz: bool = False
    has_slideshow: bool = False
    sessions: list["SessionSummary"] = []


# ---------------------------------------------------------------------------
# Quiz + adaptive slideshow (the instructional stage between the digest and
# the 8 active-recall methods)
# ---------------------------------------------------------------------------


class QuizQuestionOut(BaseModel):
    id: str
    type: Literal["multiple_choice", "short_answer"]
    concept: str
    difficulty: int
    question: str
    options: list[str] | None = None


class QuizOut(BaseModel):
    module_id: int
    threshold: float
    passed_before: bool
    questions: list[QuizQuestionOut]


class QuizAnswer(BaseModel):
    question_id: str
    response: str


class QuizSubmitRequest(BaseModel):
    answers: list[QuizAnswer]


class QuizQuestionResult(BaseModel):
    question_id: str
    concept: str
    difficulty: int
    correct: bool
    correct_answer: str
    explanation: str


class QuizSubmitResult(BaseModel):
    module_id: int
    passed: bool
    weighted_score: float
    threshold: float
    results: list[QuizQuestionResult]
    slideshow_ready: bool


class SlideshowSlideOut(BaseModel):
    concept: str
    difficulty: int
    emphasis: Literal["light", "moderate", "heavy"]
    content: str
    examples: list[str]


class SlideshowOut(BaseModel):
    module_id: int
    slides: list[SlideshowSlideOut]


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    module_id: int
    method: LearningMethod | None = None  # omit to let the method selector choose


class SessionMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    created_at: datetime


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    method_used: LearningMethod
    started_at: datetime
    completed_at: datetime | None = None
    score: int | None = None


class SessionDetail(SessionSummary):
    outcome_summary: str | None = None
    messages: list[SessionMessageOut] = []


class SessionSubmitRequest(BaseModel):
    response: str


class ExecutionResult(BaseModel):
    stdout: str
    stderr: str
    return_code: int | None = None
    timed_out: bool
    network_sandboxed: bool


class SessionSubmitResult(BaseModel):
    session_id: int
    completed: bool
    feedback: str
    score: int | None = None
    next_prompt: str | None = None  # set when the method needs another turn
    execution: ExecutionResult | None = None  # set for Ship-it sessions that ran code


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


class MonitorProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    content_type: ContentType
    method: LearningMethod
    current_weight: float
    proposed_weight: float
    rationale: str
    status: ProposalStatus


class MonitorProposalRespond(BaseModel):
    approve: bool
