from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MonitorProposal, ProposalStatus
from app.schemas import MonitorProposalOut, MonitorProposalRespond
from app.services import monitor_agent

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/proposals", response_model=list[MonitorProposalOut])
def list_proposals(db: Session = Depends(get_db)):
    proposals = (
        db.query(MonitorProposal)
        .filter(MonitorProposal.status == ProposalStatus.pending)
        .order_by(MonitorProposal.created_at.desc())
        .all()
    )
    return [MonitorProposalOut.model_validate(p) for p in proposals]


@router.post("/proposals/{proposal_id}/respond", response_model=MonitorProposalOut)
def respond_to_proposal(proposal_id: int, payload: MonitorProposalRespond, db: Session = Depends(get_db)):
    proposal = db.get(MonitorProposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status != ProposalStatus.pending:
        raise HTTPException(status_code=409, detail="Proposal already resolved")

    proposal = monitor_agent.respond_to_proposal(db, proposal, payload.approve)
    return MonitorProposalOut.model_validate(proposal)
