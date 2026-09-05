from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Program, Topic
from app.schemas import ProgramCreate, ProgramDetail, ProgramListItem, TopicListItem

router = APIRouter(prefix="/programs", tags=["programs"])


def _program_or_404(db: Session, program_id: int) -> Program:
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


@router.post("", response_model=ProgramDetail)
def create_program(payload: ProgramCreate, db: Session = Depends(get_db)):
    program = Program(title=payload.title, description=payload.description)
    db.add(program)
    db.commit()
    db.refresh(program)
    return ProgramDetail(
        id=program.id,
        title=program.title,
        description=program.description,
        created_at=program.created_at,
        topic_count=0,
        topics=[],
    )


@router.get("", response_model=list[ProgramListItem])
def list_programs(db: Session = Depends(get_db)):
    programs = db.query(Program).order_by(Program.created_at.desc()).all()
    return [
        ProgramListItem(
            id=p.id,
            title=p.title,
            description=p.description,
            created_at=p.created_at,
            topic_count=len(p.topics),
        )
        for p in programs
    ]


@router.get("/{program_id}", response_model=ProgramDetail)
def get_program(program_id: int, db: Session = Depends(get_db)):
    program = _program_or_404(db, program_id)
    topics = db.query(Topic).filter(Topic.program_id == program_id).order_by(Topic.created_at.desc()).all()
    return ProgramDetail(
        id=program.id,
        title=program.title,
        description=program.description,
        created_at=program.created_at,
        topic_count=len(topics),
        topics=[TopicListItem.model_validate(t) for t in topics],
    )


@router.delete("/{program_id}", status_code=204)
def delete_program(program_id: int, db: Session = Depends(get_db)):
    """Deletes the folder only — topics inside it are not touched, just ungrouped
    (program_id set back to null). Deleting real research/learning history as a side
    effect of tidying up a folder would be a bad surprise."""
    program = _program_or_404(db, program_id)
    db.query(Topic).filter(Topic.program_id == program_id).update({"program_id": None})
    db.delete(program)
    db.commit()
