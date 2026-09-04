from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Module
from app.schemas import ModuleDetail, SessionSummary
from app.services.research import read_digest

router = APIRouter(prefix="/topics", tags=["modules"])


@router.get("/{topic_id}/modules/{module_id}", response_model=ModuleDetail)
def get_module(topic_id: int, module_id: int, db: Session = Depends(get_db)):
    module = db.get(Module, module_id)
    if module is None or module.topic_id != topic_id:
        raise HTTPException(status_code=404, detail="Module not found")

    return ModuleDetail(
        id=module.id,
        topic_id=module.topic_id,
        order_index=module.order_index,
        title=module.title,
        one_liner=module.one_liner,
        content_type=module.content_type,
        status=module.status,
        digest_path=module.digest_path,
        digest_markdown=read_digest(module.digest_path),
        sessions=[SessionSummary.model_validate(s) for s in module.sessions],
    )
