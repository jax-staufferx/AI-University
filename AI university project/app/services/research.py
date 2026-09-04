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
from app.models import ContentType, FormatTier, Module, ModuleStatus, Topic, TopicStatus
from app.services import anthropic_client as ai
from app.services import budget

CONTEXT_HANDOFF_HEADING = "## Context Handoff"

DISAGREEMENT_INSTRUCTION = (
    "When sources disagree on a fact, definition, or best practice, say so explicitly — name the "
    "positions and who holds them — instead of silently picking one and presenting it as settled "
    "consensus."
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


def _dive_system_prompt(depth: str) -> str:
    return (
        "You are a research assistant compiling a teaching digest for a self-directed learner. "
        f"This is a {depth} pass. Produce a well-structured markdown digest that a learner could "
        "study from directly: clear sections, concrete examples, and no padding. "
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
    """Called after the user confirms continuing past the budget soft cap — picks up whatever
    research step was interrupted."""
    if topic.format_tier in (FormatTier.quick_dive, FormatTier.deep_dive):
        if not topic.digest_path:
            kickoff(db, topic)
        return

    if not topic.outline_approved:
        if not topic.outline_json:
            kickoff(db, topic)
        return

    next_pending = (
        db.query(Module)
        .filter(Module.topic_id == topic.id, Module.status == ModuleStatus.pending)
        .order_by(Module.order_index)
        .first()
    )
    if next_pending is not None:
        research_module(db, topic, next_pending)


def run_quick_dive(db: Session, topic: Topic) -> None:
    budget.check_and_increment(db, topic.id)
    digest = ai.research_call(
        system=_dive_system_prompt("quick, broad (1-2 hour single sitting)"),
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


def run_deep_dive(db: Session, topic: Topic) -> None:
    budget.check_and_increment(db, topic.id)
    digest = ai.research_call(
        system=_dive_system_prompt("thorough (a weekend's worth of study)"),
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
    for i, s in enumerate(split.get("sessions") or [{"title": topic.title, "one_liner": "Deep Dive"}]):
        db.add(
            Module(
                topic_id=topic.id,
                order_index=i,
                title=s["title"],
                one_liner=s.get("one_liner"),
                content_type=ContentType.mixed,
                status=ModuleStatus.researched,
                digest_path=digest_path,
                researched_at=datetime.now(timezone.utc),
            )
        )
    topic.status = TopicStatus.active
    db.commit()


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
            f"({_MODULE_COUNT_GUIDANCE[topic.format_tier]}).\n\n"
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
            f"target: {_MODULE_COUNT_GUIDANCE[topic.format_tier]}):\n\n{scoping_notes}\n\n"
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

    first_module = (
        db.query(Module).filter_by(topic_id=topic.id, order_index=0).one_or_none()
    )
    if first_module is not None:
        research_module(db, topic, first_module)
    return topic


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
        system=_dive_system_prompt("module-level, module-by-module") + (
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


def advance_after_module_completion(db: Session, topic: Topic, completed_module: Module) -> None:
    """Kick off research for the next pending module immediately, so it's ready when the
    learner comes back. No live-research wait mid-session."""
    next_module = (
        db.query(Module)
        .filter(Module.topic_id == topic.id, Module.order_index > completed_module.order_index)
        .order_by(Module.order_index)
        .first()
    )
    if next_module is None:
        # all modules done
        remaining = (
            db.query(Module)
            .filter(Module.topic_id == topic.id, Module.status != ModuleStatus.completed)
            .count()
        )
        if remaining == 0:
            topic.status = TopicStatus.completed
            topic.completed_at = datetime.now(timezone.utc)
            db.commit()
        return

    if next_module.status == ModuleStatus.pending:
        research_module(db, topic, next_module)
