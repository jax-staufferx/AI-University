"""Knowledge graph linking. After a topic completes, check for genuine conceptual overlap with
prior completed topics. Surface real connections; say nothing when there isn't one."""

from sqlalchemy.orm import Session

from app.models import GraphEdge, Topic, TopicStatus
from app.services import anthropic_client as ai
from app.services import budget
from app.services.research import read_digest

_SCHEMA = {
    "type": "object",
    "properties": {
        "connections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "other_topic_title": {"type": "string"},
                    "connection_note": {"type": "string"},
                },
                "required": ["other_topic_title", "connection_note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["connections"],
    "additionalProperties": False,
}


def _topic_summary(topic: Topic) -> str:
    parts = [f"Title: {topic.title}"]
    if topic.digest_path:
        digest = read_digest(topic.digest_path)
        if digest:
            parts.append(digest[:1500])
    module_titles = ", ".join(m.title for m in topic.modules)
    if module_titles:
        parts.append(f"Modules covered: {module_titles}")
    if topic.running_context:
        parts.append(topic.running_context[:1500])
    return "\n".join(parts)


def check_topic_overlap(db: Session, topic: Topic) -> list[GraphEdge]:
    others = db.query(Topic).filter(Topic.status == TopicStatus.completed, Topic.id != topic.id).all()
    if not others:
        return []

    budget.check_and_increment(db, topic.id)
    others_block = "\n\n---\n\n".join(f"[{o.title}]\n{_topic_summary(o)}" for o in others)
    result = ai.structured_call(
        system=(
            "You identify genuine conceptual overlap between a just-completed learning topic and "
            "a learner's other completed topics. Only report a connection if it's real and useful "
            "for the learner to know about — a shared underlying concept, a technique that "
            "transfers, a contrasting approach to the same problem. If there's no genuine overlap "
            "with a topic, leave it out entirely. Do not force tenuous links just to have "
            "something to say."
        ),
        user_prompt=(
            f"Just-completed topic:\n{_topic_summary(topic)}\n\n"
            f"Other completed topics:\n{others_block}\n\n"
            "Which of the other topics have a genuine conceptual connection to the just-completed "
            "one? For each real connection, name the other topic exactly as given above and "
            "explain the connection in one or two sentences. Omit any topic without a real "
            "connection."
        ),
        schema=_SCHEMA,
        max_tokens=2000,
    )

    by_title = {o.title: o for o in others}
    edges: list[GraphEdge] = []
    for c in result.get("connections") or []:
        other = by_title.get(c.get("other_topic_title", ""))
        if other is None:
            continue
        edge = GraphEdge(topic_id_a=topic.id, topic_id_b=other.id, connection_note=c["connection_note"])
        db.add(edge)
        edges.append(edge)
    if edges:
        db.commit()
    return edges
