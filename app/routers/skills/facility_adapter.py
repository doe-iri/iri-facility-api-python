from abc import ABC, abstractmethod
from . import models as skills_models


class SkillsAdapter(ABC):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER_<domain>` environment variable to install your
    facility adapter before the API starts.

    The site decides what is published. `app.routers.skills.manifest_adapter.ManifestSkillsAdapter`
    is a ready-made implementation driven by a JSON manifest.
    """

    @abstractmethod
    async def get_skills(self: "SkillsAdapter") -> list[skills_models.Skill]:
        """Return every skill to publish."""
        pass

    @abstractmethod
    async def get_skill_file(self: "SkillsAdapter", name: str, path: str) -> bytes | None:
        """Return the raw bytes of a file hosted by this API, or None if there is no such file."""
        pass
