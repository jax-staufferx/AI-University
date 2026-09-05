"""The research engine.

Quick Dive / Deep Dive: one broad upfront research pass, compiled into a digest.
Short Course / Full Course: the "curriculum brain" — scoping pass, prioritize & cut,
dependency-ordered outline, one-time approval checkpoint, then module-by-module
pre-fetch with a running context doc so later modules build on earlier ones.
"""

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import DIGESTS_DIR, settings
from app.database import SessionLocal
from app.models import ContentDepth, ContentType, FormatTier, Module, ModuleStatus, Topic, TopicStatus
from app.services import anthropic_client as ai
from app.services import budget

CONTEXT_HANDOFF_HEADING = "## Context Handoff"
DISAGREEMENT_HEADING = "## Where Sources Disagree"

DISAGREEMENT_INSTRUCTION = (
    "When sources disagree on a fact, definition, or best practice, don't silently pick one and "
    f"present it as settled consensus. Instead, include one section headed exactly '{DISAGREEMENT_HEADING}' "
    "naming the positions and who holds them. Only include this section if there is a genuine "
    "disagreement worth flagging — if sources agree, omit the section entirely rather than forcing one."
)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "untitled"


def _write_digest(topic_id: int, filename_hint: str, content: str) -> str:
    fname = f"topic{topic_id}-{_slugify(filename_hint)}.md"
    path = DIGESTS_DIR / fname
    path.write_text(content, encoding="utf-8")
    return f"digests/{fname}"


def read_digest(relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    path = DIGESTS_DIR.parent / relative_path
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _extract_context_handoff(digest_markdown: str) -> str:
    idx = digest_markdown.find(CONTEXT_HANDOFF_HEADING)
    if idx == -1:
        return ""
    return digest_markdown[idx:].strip()


def _append_running_context(topic: Topic, module_title: str, handoff: str) -> None:
    if not handoff:
        return
    entry = f"### Covered: {module_title}\n{handoff}\n"
    topic.running_context = (topic.running_context + "\n" + entry) if topic.running_context else entry


# ---------------------------------------------------------------------------
# Quick Dive / Deep Dive
# ---------------------------------------------------------------------------


_DEPTH_INSTRUCTIONS = {
    ContentDepth.beginner: (
        "Write for someone with zero background in this subject. Define every technical term in "
        "plain language the first time you use it. Favor intuition and concrete examples over "
        "exhaustive precision — it's fine to leave out edge cases and advanced nuance a beginner "
        "doesn't need yet. If in doubt, explain more, not less."
    ),
    ContentDepth.intermediate: (
        "Write for a curious, educated learner with no specialized background in this subject but "
        "comfortable with moderate complexity. Define specialized jargon on first use, but don't "
        "over-explain generally-known concepts. Cover the real mechanics, not just surface "
        "intuition, without chasing every edge case."
    ),
    ContentDepth.advanced: (
        "Write for a learner who wants real technical depth — the precision and detail a "
        "practitioner or advanced student would expect. Use field-standard terminology without "
        "over-explaining it, engage with edge cases and nuance, and don't simplify away "
        "complexity that actually matters."
    ),
}


def _dive_system_prompt(pace: str, content_depth: ContentDepth) -> str:
    return (
        "You are a research assistant compiling a teaching digest for a self-directed learner. "
        f"This is a {pace} pass. {_DEPTH_INSTRUCTIONS[content_depth]} Produce a well-structured "
        "markdown digest that a learner could study from directly: clear sections, concrete "
        "examples, and no padding. "
        f"{DISAGREEMENT_INSTRUCTION} End the digest with a '{CONTEXT_HANDOFF_HEADING}' section "
        "containing 3-6 bullet points of the key facts a follow-up study session should assume "
        "the learner already knows."
    )


def kickoff(db: Session, topic: Topic) -> None:
    """Starts whatever research step a freshly created topic needs first."""
    if topic.format_tier == FormatTier.quick_dive:
        run_quick_dive(db, topic)
    elif topic.format_tier == FormatTier.deep_dive:
        run_deep_dive(db, topic)
    else:
        generate_outline(db, topic)


def resume_pending_research(db: Session, topic: Topic) -> None:
    """Called after the user confirms continuing past the budget soft cap, for the
    synchronous cases only. Once the outline is approved, remaining module research is long
    enough that the router schedules research_all_modules_background instead of calling
    anything here — see the /budget/continue handler."""
    if topic.format_tier in (FormatTier.quick_dive, FormatTier.deep_dive):
        if not topic.digest_path:
            kickoff(db, topic)
        return

    if not topic.outline_approved and not topic.outline_json:
        kickoff(db, topic)


def run_quick_dive(db: Session, topic: Topic) -> None:
    budget.check_and_increment(db, topic.id)
    digest = ai.research_call(
        system=_dive_system_prompt("quick, broad (1-2 hour single sitting)", topic.depth),
        user_prompt=(
            f"Research the topic '{topic.title}' broadly enough for someone to get a working "
            "understanding in one sitting. Cover: what it is, why it matters, the core concepts "
            "in the order they should be learned, common misconceptions, and one or two worked "
            "examples."
        ),
        max_tokens=8000,
        effort="medium",
        max_search_uses=6,
    )
    digest_path = _write_digest(topic.id, topic.title, digest)

    module = Module(
        topic_id=topic.id,
        order_index=0,
        title=topic.title,
        one_liner="Quick Dive digest",
        content_type=ContentType.mixed,
        status=ModuleStatus.researched,
        digest_path=digest_path,
        researched_at=datetime.now(timezone.utc),
    )
    db.add(module)
    topic.digest_path = digest_path
    topic.status = TopicStatus.active
    db.commit()

    from app.services import quiz as quiz_service

    quiz_service.generate_quiz(db, module)


def run_deep_dive(db: Session, topic: Topic) -> None:
    budget.check_and_increment(db, topic.id)
    digest = ai.research_call(
        system=_dive_system_prompt("thorough (a weekend's worth of study)", topic.depth),
        user_prompt=(
            f"Research the topic '{topic.title}' thoroughly enough for a weekend of focused study. "
            "Cover foundational concepts through to practical application, with enough depth that "
            "someone could hold their own in a conversation with a practitioner afterward. Include "
            "worked examples and note where hands-on practice would help."
        ),
        max_tokens=16000,
        effort="high",
        max_search_uses=10,
    )
    digest_path = _write_digest(topic.id, topic.title, digest)

    budget.check_and_increment(db, topic.id)
    split = ai.structured_call(
        system="You split a research digest into a short sequence of self-contained study sessions.",
        user_prompt=(
            f"Here is a research digest on '{topic.title}':\n\n{digest}\n\n"
            "Split this into 2-3 sessions for a weekend of study, each with a practice round in mind. "
            "Sessions should build on each other. Give each a title and a one-liner describing which "
            "part of the digest it focuses on."
        ),
        schema={
            "type": "object",
            "properties": {
                "sessions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "one_liner": {"type": "string"},
                        },
                        "required": ["title", "one_liner"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["sessions"],
            "additionalProperties": False,
        },
        max_tokens=2000,
    )

    topic.digest_path = digest_path
    new_modules = []
    for i, s in enumerate(split.get("sessions") or [{"title": topic.title, "one_liner": "Deep Dive"}]):
        m = Module(
            topic_id=topic.id,
            order_index=i,
            title=s["title"],
            one_liner=s.get("one_liner"),
            content_type=ContentType.mixed,
            status=ModuleStatus.researched,
            digest_path=digest_path,
            researched_at=datetime.now(timezone.utc),
        )
        db.add(m)
        new_modules.append(m)
    topic.status = TopicStatus.active
    db.commit()

    from app.services import quiz as quiz_service

    for m in new_modules:
        quiz_service.generate_quiz(db, m)


# ---------------------------------------------------------------------------
# Short Course / Full Course — the curriculum brain
# ---------------------------------------------------------------------------

_MODULE_COUNT_GUIDANCE = {
    FormatTier.short_course: "4-5 modules, each roughly 45-75 minutes of study (about a week total)",
    FormatTier.full_course: (
        "as many modules as the subject genuinely needs for a realistic 2-3 week self-study "
        "course (commonly 8-16), each roughly 45-90 minutes"
    ),
}

_OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "modules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "one_liner": {"type": "string"},
                    "content_type": {"type": "string", "enum": ["skill", "conceptual", "mixed"]},
                    "prerequisite_titles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Titles of other modules in this same list that must come before this one.",
                    },
                },
                "required": ["title", "one_liner", "content_type", "prerequisite_titles"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["modules"],
    "additionalProperties": False,
}


def _topo_sort(modules: list[dict]) -> list[dict]:
    """Order modules by prerequisite_titles (Kahn's algorithm). Falls back to input order on
    unresolvable references or cycles rather than dropping modules."""
    by_title = {m["title"]: m for m in modules}
    indegree = {m["title"]: 0 for m in modules}
    edges: dict[str, list[str]] = {m["title"]: [] for m in modules}

    for m in modules:
        for prereq in m.get("prerequisite_titles") or []:
            if prereq in by_title and prereq != m["title"]:
                edges[prereq].append(m["title"])
                indegree[m["title"]] += 1

    queue = [m["title"] for m in modules if indegree[m["title"]] == 0]
    ordered: list[str] = []
    while queue:
        # stable: prefer original relative order among ready nodes
        queue.sort(key=lambda t: [m["title"] for m in modules].index(t))
        title = queue.pop(0)
        ordered.append(title)
        for nxt in edges[title]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(ordered) != len(modules):
        # cycle detected — fall back to the model's original order
        return modules
    return [by_title[t] for t in ordered]


def generate_outline(db: Session, topic: Topic) -> list[dict]:
    """Runs the scoping pass + prioritize/cut, then dependency-orders the result.
    Stores the proposed outline on the topic (not yet approved) and returns it."""
    budget.check_and_increment(db, topic.id)
    scoping_notes = ai.research_call(
        system=(
            "You are scoping a self-study curriculum. Research how this subject is actually taught "
            "by people who know it — university syllabi, respected online courses, standard textbook "
            "tables of contents. Anchor your findings to how the field organizes itself, not free "
            "association. Then identify the core pillars and rank them must-know vs nice-to-know for "
            "a learner on a real time budget."
        ),
        user_prompt=(
            f"Topic: '{topic.title}'. Format: {topic.format_tier.value} "
            f"({_MODULE_COUNT_GUIDANCE[topic.format_tier]}). Target depth: {topic.depth.value} — "
            f"{_DEPTH_INSTRUCTIONS[topic.depth]}\n\n"
            "Research: (1) how this subject is structured in real courses/syllabi/textbooks, "
            "(2) the core pillars ranked must-know vs nice-to-know, (3) real prerequisite "
            "relationships between the pillars. Write up your findings as notes — this will be "
            "turned into a module list next, so be concrete about ordering and dependencies."
        ),
        max_tokens=10000,
        effort="high",
        max_search_uses=10,
    )

    outline = ai.structured_call(
        system=(
            "You turn curriculum scoping notes into a concrete, dependency-ordered module list. "
            "Cut to a realistic module count for the time box given — the goal is nothing important "
            "skipped, not covering literally everything."
        ),
        user_prompt=(
            f"Scoping notes for '{topic.title}' ({topic.format_tier.value}, "
            f"target: {_MODULE_COUNT_GUIDANCE[topic.format_tier]}, depth: {topic.depth.value}):\n\n"
            f"{scoping_notes}\n\n"
            "Produce the module list. Each module needs a title, a one-line description, a "
            "content_type (skill = hands-on/practice-heavy, conceptual = ideas/theory, mixed = both), "
            "and prerequisite_titles referencing other module titles in this same list that must be "
            "learned first (empty list if none)."
        ),
        schema=_OUTLINE_SCHEMA,
        max_tokens=6000,
        effort="high",
    )

    ordered = _topo_sort(outline.get("modules") or [])

    import json

    topic.outline_json = json.dumps(ordered)
    topic.status = TopicStatus.planning
    db.commit()
    return ordered


def approve_outline(db: Session, topic: Topic, modules_override: list[dict] | None = None) -> Topic:
    import json

    modules = modules_override if modules_override is not None else json.loads(topic.outline_json or "[]")

    for i, m in enumerate(modules):
        db.add(
            Module(
                topic_id=topic.id,
                order_index=i,
                title=m["title"],
                one_liner=m.get("one_liner"),
                content_type=ContentType(m.get("content_type", "mixed")),
                status=ModuleStatus.pending,
            )
        )
    topic.outline_approved = True
    topic.status = TopicStatus.active
    db.commit()
    db.refresh(topic)
    return topic


def research_all_pending_modules(db: Session, topic: Topic) -> None:
    """Researches every still-pending module in order, each building on the running context
    from the ones before it — the full course (all digests and quizzes) ends up ready before
    the learner starts module 1. Modules stay locked in the UI regardless (see
    is_module_unlocked) until earlier ones are completed; this only removes the research wait.
    Raises BudgetExceeded on whichever module hits the cap — everything before it stays done."""
    pending = (
        db.query(Module)
        .filter(Module.topic_id == topic.id, Module.digest_path.is_(None))
        .order_by(Module.order_index)
        .all()
    )
    for m in pending:
        research_module(db, topic, m)


def research_all_modules_background(topic_id: int) -> None:
    """FastAPI BackgroundTask entry point — runs after the HTTP response has already gone
    out (the whole point: a full course can take minutes to research). Opens its own DB
    session since the request-scoped one is closed by the time this runs.

    There's no HTTP request left to raise an error back to, so every failure mode has to end
    quietly here: the budget cap stops silently (the frontend sees that via budget_cap_hit
    and resumes explicitly), and anything else — a bad API key, no credits, a network error —
    gets recorded on topic.research_error instead of crashing the background task and leaving
    modules_researched stuck below modules_total forever with no explanation."""
    db = SessionLocal()
    try:
        topic = db.get(Topic, topic_id)
        if topic is None:
            return
        topic.research_error = None
        db.commit()
        try:
            research_all_pending_modules(db, topic)
        except budget.BudgetExceeded:
            pass
        except Exception as e:
            topic.research_error = str(e)[:2000]
            db.commit()
    finally:
        db.close()


def is_module_unlocked(module: Module) -> bool:
    """Quick Dive is always a single module, always unlocked once researched. Everything else
    (Deep Dive, Short Course, Full Course) unlocks sequentially — a module is available only
    once every module before it in the same topic is completed."""
    if module.topic.format_tier == FormatTier.quick_dive:
        return True
    return all(
        sibling.status == ModuleStatus.completed
        for sibling in module.topic.modules
        if sibling.order_index < module.order_index
    )


def research_module(db: Session, topic: Topic, module: Module) -> None:
    if module.digest_path:
        return  # already researched

    budget.check_and_increment(db, topic.id)
    context_block = (
        f"\n\nWhat has already been covered in earlier modules (assume the learner knows this; "
        f"don't re-teach it, build on it):\n{topic.running_context}"
        if topic.running_context
        else ""
    )
    digest = ai.research_call(
        system=_dive_system_prompt("module-level, module-by-module", topic.depth) + (
            " This module is part of a larger course — write it assuming the learner has completed "
            "the earlier modules, and don't repeat material already covered."
        ),
        user_prompt=(
            f"Course: '{topic.title}'. Module: '{module.title}' — {module.one_liner}. "
            f"Content type: {module.content_type.value}."
            f"{context_block}\n\n"
            "Research and write a teaching digest for this module specifically."
        ),
        max_tokens=9000,
        effort="medium",
        max_search_uses=8,
    )
    digest_path = _write_digest(topic.id, f"{module.order_index}-{module.title}", digest)

    module.digest_path = digest_path
    module.status = ModuleStatus.researched
    module.researched_at = datetime.now(timezone.utc)
    _append_running_context(topic, module.title, _extract_context_handoff(digest))
    db.commit()

    from app.services import quiz as quiz_service

    quiz_service.generate_quiz(db, module)


def advance_after_module_completion(db: Session, topic: Topic, completed_module: Module) -> None:
    """Checks whether the topic is now fully completed. Research for every module already
    happened upfront (course tiers, in the background) or at topic creation (Quick/Deep
    Dive) — modules simply unlock in sequence as earlier ones complete (is_module_unlocked),
    so there's nothing left to kick off here."""
    remaining = (
        db.query(Module).filter(Module.topic_id == topic.id, Module.status != ModuleStatus.completed).count()
    )
    if remaining == 0:
        topic.status = TopicStatus.completed
        topic.completed_at = datetime.now(timezone.utc)
        db.commit()
