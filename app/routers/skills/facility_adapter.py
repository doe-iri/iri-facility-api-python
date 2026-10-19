from abc import ABC, abstractmethod
from . import models as skills_models


class SkillsAdapter(ABC):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER_<domain>` environment variable to install your
    facility adapter before the API starts.

    `app.routers.skills.directory_adapter.DirectorySkillsAdapter` is a ready-made
    implementation that serves skills from a directory on disk.
    """

    @abstractmethod
    async def list_skills(
        self: "SkillsAdapter",
        modified_since: str | None = None,
        name: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[skills_models.SkillSummary]:
        pass

    @abstractmethod
    async def get_skill(
        self: "SkillsAdapter",
        skill_id: str,
        modified_since: str | None = None,
    ) -> skills_models.Skill | None:
        pass
