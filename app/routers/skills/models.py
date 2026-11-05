"""Skills-related models.

Responses follow the index format of the Agent Skills Discovery draft v0.2.0
(https://github.com/cloudflare/agent-skills-discovery-rfc), served at /skills rather
than a well-known path. Two things are added to that format, which clients must ignore
if they do not recognize them. `files` points at each file of a multi-file skill, which
the draft would otherwise distribute as an archive. `self_uri` and `_links` are the HAL
hypermedia every IRI representation carries.
"""
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ...request_context import get_url_prefix
from ...types.hal import IRI_CURIE, PROFILE_SKILL, build_hal_link

SKILLS_INDEX_SCHEMA = "https://schemas.agentskills.io/discovery/0.2.0/schema.json"
SKILL_FILE_NAME = "SKILL.md"

_NAME_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


def _hosted_url(skill_name: str, path: str) -> str:
    return f"{get_url_prefix()}/skills/{skill_name}/{quote(path)}"


class SkillFile(BaseModel):
    """One file of a skill, hosted by this API."""

    skill_name: str = Field(..., exclude=True, description="Name of the skill this file belongs to.")
    path: str = Field(..., description="POSIX path relative to the skill root.", example="scripts/esnet_iri_client.py")
    digest: str = Field(..., pattern=_DIGEST_PATTERN, description="SHA-256 of the file's raw bytes, as `sha256:{hex}`.")
    executable: bool = Field(default=False, description="Whether the source file has its executable bit set. This records the file mode and does not ask a client to run it.")

    @computed_field(description="URL of the file's raw bytes.")
    @property
    def url(self) -> str:
        return _hosted_url(self.skill_name, self.path)


class Skill(BaseModel):
    """One skill in the index. `url` and `digest` identify its artifact; `files` lists each file when this API hosts them."""

    # Forbidding unknown fields makes a typo in site input fail at startup instead of being dropped silently.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(..., pattern=_NAME_PATTERN, max_length=64, description="Skill identifier: lowercase alphanumerics and single hyphens.", example="esnet-iri-facility-api")
    type: Literal["skill-md", "archive"] = Field(default="skill-md", description="Artifact type: a single SKILL.md, or a bundled archive.")
    description: str = Field(..., min_length=1, max_length=1024, description="What the skill does and when to use it.")
    digest: str = Field(..., pattern=_DIGEST_PATTERN, description="SHA-256 of the raw bytes at `url`, as `sha256:{hex}`.")
    files: list[SkillFile] | None = Field(default=None, description="Each file hosted by this API, SKILL.md first. Absent when the site hosts the skill elsewhere.")
    external_url: str | None = Field(default=None, min_length=1, exclude=True, validation_alias="url", description="Artifact location when the site hosts the skill elsewhere.")

    @computed_field(description="URL of the skill artifact.")
    @property
    def url(self) -> str:
        return self.external_url or _hosted_url(self.name, SKILL_FILE_NAME)

    @computed_field(description="The canonical URL of this skill's index entry.")
    @property
    def self_uri(self) -> str:
        return f"{get_url_prefix()}/skills/{self.name}"

    @computed_field(description="HAL hypermedia links for this representation.")
    @property
    def _links(self) -> dict:
        return {"self": build_hal_link(self.self_uri, profile=PROFILE_SKILL), "curies": [IRI_CURIE]}


class SkillsIndex(BaseModel):
    """Every skill this facility publishes."""

    model_config = ConfigDict(populate_by_name=True)

    schema_uri: str = Field(default=SKILLS_INDEX_SCHEMA, alias="$schema", description="Identifies the index format version.")
    skills: list[Skill] = Field(default_factory=list, description="The published skills.")

    @computed_field(description="HAL hypermedia links for this representation.")
    @property
    def _links(self) -> dict:
        links: dict = {"self": build_hal_link(f"{get_url_prefix()}/skills"), "curies": [IRI_CURIE]}
        if self.skills:
            links["iri:has-skill"] = [build_hal_link(skill.self_uri, profile=PROFILE_SKILL) for skill in self.skills]
        return links
