"""Lab status aggregation API endpoint.

Read-only endpoint for day-2 operations. Summarises project operational
state, RDMP health, and unresolved remediation tasks at the lab level.
No enforcement logic — purely advisory.

FROZEN for v0.5 (PR #6) — response schema and endpoint contract are
stable. Bug fixes only until v0.6.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.models.supervisor_membership import SupervisorRole
from supervisor.api.deps import get_current_active_user, require_supervisor_role
from supervisor.services.lab_status_service import compute_lab_status


router = APIRouter()


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class OperationalStateSchema(BaseModel):
    operational: int
    non_operational: int


class RDMPStatusSchema(BaseModel):
    no_rdmp: int
    draft: int
    active: int
    superseded: int


class ProjectSummarySchema(BaseModel):
    total_projects: int
    by_operational_state: OperationalStateSchema
    by_rdmp_status: RDMPStatusSchema


class NeedsAttentionSchema(BaseModel):
    type: str
    severity: str
    count: int
    entity_type: str
    entity_ids: list[int]
    message: str


class RemediationSummarySchema(BaseModel):
    total_open: int
    by_severity: dict[str, int]


class LabStatusResponse(BaseModel):
    projects: ProjectSummarySchema
    needs_attention: list[NeedsAttentionSchema]
    remediation_summary: RemediationSummarySchema


# -------------------------------------------------------------------------
# Endpoint
# -------------------------------------------------------------------------

@router.get(
    "/{supervisor_id}/status-summary",
    response_model=LabStatusResponse,
)
def get_lab_status_summary(
    supervisor_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get lab operational status summary and needs-attention items.

    Returns project counts by operational state and RDMP status,
    conditions requiring Steward/PI attention, and a remediation summary.

    Accessible to PI and STEWARD only. Researcher access is denied
    because this endpoint surfaces lab-wide operational details that
    are outside the researcher role's responsibilities.
    """
    # Verify lab exists
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab not found",
        )

    # PI and STEWARD only; researcher is denied.
    require_supervisor_role(
        db, current_user, supervisor_id,
        [SupervisorRole.PI, SupervisorRole.STEWARD],
    )

    result = compute_lab_status(db, supervisor_id)

    return LabStatusResponse(
        projects=ProjectSummarySchema(
            total_projects=result.projects.total_projects,
            by_operational_state=OperationalStateSchema(
                **result.projects.by_operational_state,
            ),
            by_rdmp_status=RDMPStatusSchema(
                **result.projects.by_rdmp_status,
            ),
        ),
        needs_attention=[
            NeedsAttentionSchema(
                type=item.type,
                severity=item.severity,
                count=item.count,
                entity_type=item.entity_type,
                entity_ids=item.entity_ids,
                message=item.message,
            )
            for item in result.needs_attention
        ],
        remediation_summary=RemediationSummarySchema(
            total_open=result.remediation_summary.total_open,
            by_severity=result.remediation_summary.by_severity,
        ),
    )
