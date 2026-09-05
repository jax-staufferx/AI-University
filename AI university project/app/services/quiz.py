"""Diagnostic quiz: the gate between reading the digest and unlocking the 8 active-recall
methods. Generated once per module alongside its digest. Multiple-choice questions grade
deterministically; short-answer questions are graded by a single batched Claude call.

Difficulty (1-10, assigned per question at generation time) does double duty:
- Pass/fail threshold: a straightforward difficulty-weighted score (harder questions worth more).
- Slideshow emphasis (see slideshow.py): the OPPOSITE signal — missing an easy question is the
  bigger red flag (a real gap), so it gets more re-teaching than a missed hard question.
"""

import json
import uuid

from sqlalchemy.orm import Session

from app.models import Module
from app.schemas import QuizAnswer, QuizOut, QuizQuestionOut, QuizQuestionResult, QuizSubmitResult
from app.services import anthropic_client as ai
from app.services import budget
from app.services.research import _DEPTH_INSTRUCTIONS, _learner_context_block, read_digest

QUIZ_PASS_THRESHOLD = 0.2

_DIFFICULTY_RUBRIC = (
    "Difficulty is 1-10, assigned per question:\n"
    "1-2: pure recall of a fact stated directly in the digest, no reasoning needed.\n"
    "3-4: restating a relationship between two facts the digest states explicitly.\n"
    "5-6: applying the concept somewhere new, or explaining why (not just what).\n"
    "7-8: combining multiple concepts, or a point the digest flags as commonly confused.\n"
    "9-10: flagged source disagreements, counterintuitive results, or things requiring several "
    "qualifications held at once."
)

_QUIZ_GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["multiple_choice", "short_answer"]},
                    "concept": {
                        "type": "string",
                        "description": "Short label for the specific point this tests, matching the digest's own terms.",
                    },
                    "difficulty": {"type": "integer"},
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Exactly 4 plausible options for multiple_choice. Empty array for short_answer.",
                    },
                    "correct_answer": {
                        "type": "string",
                        "description": (
                            "For multiple_choice: must exactly match one of the options strings. "
                            "For short_answer: a concise model answer / rubric of what a correct "
                            "answer must contain."
                        ),
                    },
                },
                "required": ["type", "concept", "difficulty", "question", "options", "correct_answer"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}

_SHORT_ANSWER_GRADING_SCHEMA = {
    "type": "object",
    "properties": {
        "judgments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "correct": {"type": "boolean"},
                    "explanation": {
                        "type": "string",
                        "description": "One or two sentences, direct, tied to the model answer.",
                    },
                },
                "required": ["question_id", "correct", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["judgments"],
    "additionalProperties": False,
}


def generate_quiz(db: Session, module: Module) -> None:
    if module.quiz_json:
        return  # already generated

    digest = read_digest(module.digest_path) or "(no digest available)"
    depth = module.topic.depth
    budget.check_and_increment(db, module.topic_id)
    result = ai.structured_call(
        system=(
            "You write a diagnostic quiz that checks whether a learner actually absorbed a "
            "study digest before they move on to practice exercises. Cover the digest's core "
            "points, not trivia. Mix multiple_choice and short_answer questions — use "
            "short_answer for anything that requires explaining a relationship or reasoning, "
            "not just naming a fact. Match the learner's chosen depth: " + _DEPTH_INSTRUCTIONS[depth] + " "
            + _DIFFICULTY_RUBRIC
        ),
        user_prompt=(
            f"Module: {module.title} — {module.one_liner}\n\nDigest:\n{digest}\n\n"
            "Write 6-9 questions covering this digest's core points, spanning the full "
            "difficulty range — don't make them all easy or all hard. Each multiple_choice "
            "question needs exactly 4 options." + _learner_context_block(module.topic)
        ),
        schema=_QUIZ_GENERATION_SCHEMA,
        max_tokens=4000,
        effort="medium",
    )

    questions = []
    for q in result.get("questions") or []:
        questions.append(
            {
                "id": uuid.uuid4().hex[:8],
                "type": q["type"],
                "concept": q["concept"],
                "difficulty": max(1, min(10, int(q["difficulty"]))),
                "question": q["question"],
                "options": q.get("options") or None,
                "correct_answer": q["correct_answer"],
            }
        )

    module.quiz_json = json.dumps({"questions": questions})
    db.commit()


def get_quiz_for_frontend(module: Module) -> QuizOut:
    stored = json.loads(module.quiz_json or '{"questions": []}')
    questions = [
        QuizQuestionOut(
            id=q["id"],
            type=q["type"],
            concept=q["concept"],
            difficulty=q["difficulty"],
            question=q["question"],
            options=q.get("options"),
        )
        for q in stored["questions"]
    ]
    return QuizOut(
        module_id=module.id,
        threshold=QUIZ_PASS_THRESHOLD,
        passed_before=module.quiz_passed,
        questions=questions,
    )


def grade_quiz(db: Session, module: Module, answers: list[QuizAnswer]) -> QuizSubmitResult:
    stored = json.loads(module.quiz_json or '{"questions": []}')["questions"]
    answers_by_id = {a.question_id: a.response for a in answers}

    results: dict[str, QuizQuestionResult] = {}
    short_answer_batch = []

    for q in stored:
        response = answers_by_id.get(q["id"], "")
        if q["type"] == "multiple_choice":
            correct = response.strip().lower() == q["correct_answer"].strip().lower()
            results[q["id"]] = QuizQuestionResult(
                question_id=q["id"],
                concept=q["concept"],
                difficulty=q["difficulty"],
                correct=correct,
                correct_answer=q["correct_answer"],
                explanation="Correct." if correct else f"The correct answer is: {q['correct_answer']}",
            )
        else:
            short_answer_batch.append((q, response))

    if short_answer_batch:
        budget.check_and_increment(db, module.topic_id)
        batch_prompt = "\n\n".join(
            f"Question ID: {q['id']}\nQuestion: {q['question']}\nModel answer/rubric: {q['correct_answer']}\n"
            f"Learner's answer: {response}"
            for q, response in short_answer_batch
        )
        judged = ai.structured_call(
            system=(
                "You grade short-answer quiz responses against a model answer/rubric. Be strict "
                "but fair — the learner doesn't need the exact wording, but needs to demonstrate "
                "the same understanding. Judge each question independently."
            ),
            user_prompt=batch_prompt,
            schema=_SHORT_ANSWER_GRADING_SCHEMA,
            max_tokens=3000,
            effort="medium",
        )
        judgments = {j["question_id"]: j for j in judged.get("judgments") or []}
        for q, response in short_answer_batch:
            j = judgments.get(q["id"])
            results[q["id"]] = QuizQuestionResult(
                question_id=q["id"],
                concept=q["concept"],
                difficulty=q["difficulty"],
                correct=bool(j and j.get("correct")),
                correct_answer=q["correct_answer"],
                explanation=(j["explanation"] if j else "Not graded — no response received."),
            )

    total_weight = sum(q["difficulty"] for q in stored) or 1
    earned_weight = sum(q["difficulty"] for q in stored if results[q["id"]].correct)
    weighted_score = earned_weight / total_weight
    passed = weighted_score >= QUIZ_PASS_THRESHOLD

    if passed and not module.quiz_passed:
        module.quiz_passed = True

    submit_result = QuizSubmitResult(
        module_id=module.id,
        passed=passed,
        weighted_score=round(weighted_score, 3),
        threshold=QUIZ_PASS_THRESHOLD,
        results=[results[q["id"]] for q in stored],
        slideshow_ready=module.quiz_passed,
    )
    module.quiz_last_result_json = submit_result.model_dump_json()
    db.commit()

    return submit_result


def get_last_quiz_result(module: Module) -> QuizSubmitResult | None:
    if not module.quiz_last_result_json:
        return None
    return QuizSubmitResult.model_validate_json(module.quiz_last_result_json)
