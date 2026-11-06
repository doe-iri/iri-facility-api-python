from fastapi import Depends, HTTPException, Request, Response

from ...types.http import forbidExtraQueryParams
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from . import facility_adapter, models

router = iri_router.IriRouter(facility_adapter.SkillsAdapter, prefix="/skills", tags=["skills"])

_FILE_MEDIA_TYPES = ("text/markdown", "text/plain", "application/octet-stream")


def _media_type(path: str, data: bytes) -> str:
    """Pick a type that browsers will not render, so a listed HTML file cannot run on the API origin."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    return "text/markdown" if path.endswith(".md") else "text/plain"


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
async def get_skills(
    request: Request,
    _forbid=Depends(forbidExtraQueryParams()),
) -> models.SkillsIndex:
    """Get the index of agent skills published by this facility"""
    return models.SkillsIndex(skills=await router.adapter.get_skills())


@router.get("/{name}", responses=DEFAULT_RESPONSES, operation_id="getSkill", response_model_exclude_none=True, openapi_extra=iri_meta_dict("development", "optional"))
async def get_skill(
    request: Request,
    name: str,
    _forbid=Depends(forbidExtraQueryParams()),
) -> models.Skill:
    """Get one skill's index entry by name"""
    skill = next((s for s in await router.adapter.get_skills() if s.name == name), None)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.get("/{name}/{path:path}",
            response_class=Response,
            responses={200: {"description": "The file's raw bytes", "content": {media_type: {} for media_type in _FILE_MEDIA_TYPES}}, **DEFAULT_RESPONSES},
            operation_id="getSkillFile",
            openapi_extra=iri_meta_dict("development", "optional"))
async def get_skill_file(
    request: Request,
    name: str,
    path: str,
    _forbid=Depends(forbidExtraQueryParams()),
) -> Response:
    """Get the raw bytes of one file listed by a skill"""
    data = await router.adapter.get_skill_file(name, path)
    if data is None:
        raise HTTPException(status_code=404, detail="Skill file not found")
    return Response(content=data, media_type=_media_type(path, data), headers={"X-Content-Type-Options": "nosniff"})
