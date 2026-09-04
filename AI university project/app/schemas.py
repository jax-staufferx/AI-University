from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ContentType, FormatTier, LearningMethod, ModuleStatus, ProposalStatus, TopicStatus

# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


class TopicCreate(BaseModel):
    title: str
    format_tier: FormatTier


class TopicListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    format_tier: FormatTier
    status: TopicStatus
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
    status: TopicStatus
    created_at: datetime
    completed_at: datetime | None = None
    digest_path: str | None = None
    outline_approved: bool
    current_module_id: int | None = None
    modules: list[ModuleSummary] = []
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
    digest_path: str | None = None
    digest_markdown: str | None = None
    sessions: list["SessionSummary"] = []


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


class SessionSubmitResult(BaseModel):
    session_id: int
    completed: bool
    feedback: str
    score: int | None = None
    next_prompt: str | None = None  # set when the method needs another turn


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
