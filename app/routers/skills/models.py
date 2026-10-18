"""Skills-related models.

A skill is an Agent Skill bundle (a directory with a SKILL.md plus optional
references/ and scripts/ files). The full Skill representation carries every
file inline so a client can reconstruct the directory from a single response,
with no further fetches.
"""
from typing import Literal

from pydantic import BaseModel, Field

from ...types.base import NamedObject
from ...types.hal import PROFILE_SKILL


class SkillSummary(NamedObject):
    """Skill metadata. `name` and `description` come from the SKILL.md frontmatter."""

    def _self_path(self) -> str:
        return f"/skills/{self.id}"

    def _link_profile(self) -> str | None:
        return PROFILE_SKILL

    id: str = Field(..., description="Skill identifier: the skill directory name.", example="esnet-iri-facility-api")


class SkillFile(BaseModel):
    """One file of a skill bundle, with its content inline."""

    path: str = Field(..., description="POSIX path relative to the skill directory.", example="scripts/esnet_iri_client.py")
    encoding: Literal["utf-8", "base64"] = Field(..., description="How `content` is encoded: `utf-8` text as-is, or `base64` of the raw bytes.", example="utf-8")
    content: str = Field(..., description="File content, encoded as given by `encoding`.")
    executable: bool = Field(default=False, description="Whether the file should be marked executable when written to disk.")


class Skill(SkillSummary):
    """A complete skill bundle. `files` holds every file of the skill, SKILL.md first, the rest sorted by path."""

    files: list[SkillFile] = Field(default_factory=list, description="All files of the skill, content inline. SKILL.md is first.")
