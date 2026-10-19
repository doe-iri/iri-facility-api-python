from fastapi import Depends, Query, Request, HTTPException

from ...types.http import forbidExtraQueryParams
from ...types.scalars import StrictDateTime
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from . import facility_adapter, models

router = iri_router.IriRouter(facility_adapter.SkillsAdapter, prefix="/skills", tags=["skills"])


@router.get("",
            responses=DEFAULT_RESPONSES,
            operation_id="getSkills",
            response_model_exclude_none=True,
            openapi_extra=iri_meta_dict("development", "optional"))
@router.get("/",
            responses=DEFAULT_RESPONSES,
            operation_id="getSkillsWithSlash",
            response_model_exclude_none=True,
            include_in_schema=False)
async def list_skills(
    request: Request,
    modified_since: StrictDateTime = Query(default=None),
    name: str | None = Query(default=None, min_length=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, le=1000),
    _forbid=Depends(forbidExtraQueryParams("modified_since", "name", "offset", "limit")),
) -> list[models.SkillSummary]:
    """List the agent skills published by this facility (metadata only; fetch a skill for its files)"""
    return await router.adapter.list_skills(modified_since=modified_since, name=name, offset=offset, limit=limit)


@router.get("/{skill_id}", responses=DEFAULT_RESPONSES, operation_id="getSkill", response_model_exclude_none=True, openapi_extra=iri_meta_dict("development", "optional"))
async def get_skill(
    request: Request,
    skill_id: str,
    modified_since: StrictDateTime = Query(default=None),
    _forbid=Depends(forbidExtraQueryParams("modified_since")),
) -> models.Skill:
    """Get a complete skill bundle by ID, with every file (SKILL.md, references, scripts) inline"""
    skill = await router.adapter.get_skill(skill_id=skill_id, modified_since=modified_since)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill
