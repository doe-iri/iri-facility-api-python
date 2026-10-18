"""Generic skills adapter that serves Agent Skills from a directory on disk.

Every immediate subdirectory of the skills root that contains a SKILL.md is one
skill; the directory name is the skill id. All files of the skill (SKILL.md,
references/, scripts/, ...) are loaded once at startup and returned inline by
get_skill, so a client never has to fetch a script from anywhere else.

Configure with `IRI_API_ADAPTER_skills=app.routers.skills.directory_adapter.DirectorySkillsAdapter`
and `IRI_SKILLS_DIR=/path/to/skills`. Subclasses may pass `skills_dir` instead.
"""
import base64
import datetime
import os
import stat
from pathlib import Path

from ...apilogger import get_stream_logger
from ...types.base import NamedObject
from . import models as skills_models
from .facility_adapter import SkillsAdapter

LOGGER = get_stream_logger(__name__)

SKILL_FILE_NAME = "SKILL.md"


def _skip_name(name: str) -> bool:
    return name.startswith(".") or name == "__pycache__" or name.endswith(".pyc")


def frontmatter_value(text: str, key: str) -> str | None:
    """Return a top-level `key: value` line from the SKILL.md frontmatter, or None.

    Not a YAML parser: SKILL.md is served as-is, only name/description are surfaced for listing.
    """
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith(f"{key}:"):
            return line[len(key) + 1:].strip().strip("'\"") or None
    return None


def _load_file(skill_dir: Path, path: Path) -> skills_models.SkillFile:
    data = path.read_bytes()
    try:
        content, encoding = data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        content, encoding = base64.b64encode(data).decode("ascii"), "base64"
    return skills_models.SkillFile(
        path=path.relative_to(skill_dir).as_posix(),
        encoding=encoding,
        content=content,
        executable=bool(path.stat().st_mode & stat.S_IXUSR),
    )


def load_skill(skill_dir: Path) -> skills_models.Skill:
    """Load every regular file of a skill directory, skipping hidden files and symlinks."""
    files, newest = [], 0.0
    for dirpath, dirnames, filenames in os.walk(skill_dir):
        dirnames[:] = [d for d in dirnames if not _skip_name(d)]
        for filename in filenames:
            path = Path(dirpath, filename)
            # Symlinks could point outside the skill directory; only plain files are served.
            if _skip_name(filename) or path.is_symlink() or not path.is_file():
                continue
            files.append(_load_file(skill_dir, path))
            newest = max(newest, path.stat().st_mtime)
    files.sort(key=lambda f: (f.path != SKILL_FILE_NAME, f.path))
    skill_md = files[0].content if files and files[0].path == SKILL_FILE_NAME else ""
    return skills_models.Skill(
        id=skill_dir.name,
        name=frontmatter_value(skill_md, "name") or skill_dir.name,
        description=frontmatter_value(skill_md, "description"),
        last_modified=datetime.datetime.fromtimestamp(newest, tz=datetime.timezone.utc),
        files=files,
    )


class DirectorySkillsAdapter(SkillsAdapter):
    """Serve every skill found under a directory, loaded and cached at construction."""

    def __init__(self, skills_dir: str | os.PathLike | None = None):
        root = skills_dir if skills_dir is not None else os.environ.get("IRI_SKILLS_DIR")
        self.skills_dir = Path(root) if root else None
        self._skills = self._load_all()

    def _load_all(self) -> list[skills_models.Skill]:
        if self.skills_dir is None or not self.skills_dir.is_dir():
            LOGGER.warning("Skills directory %s not found (set IRI_SKILLS_DIR); serving zero skills", self.skills_dir)
            return []
        skills = []
        for entry in sorted(self.skills_dir.iterdir()):
            if _skip_name(entry.name) or entry.is_symlink() or not (entry / SKILL_FILE_NAME).is_file():
                continue
            try:
                skills.append(load_skill(entry))
            except (OSError, ValueError) as exc:
                LOGGER.warning("Skipping skill directory '%s': %s", entry.name, exc)
        LOGGER.info("Loaded %d skill(s) from %s: %s", len(skills), self.skills_dir, [s.id for s in skills])
        return skills

    async def list_skills(
        self: "DirectorySkillsAdapter",
        modified_since: str | None = None,
        name: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[skills_models.SkillSummary]:
        items = skills_models.SkillSummary.find(self._skills, name=name, modified_since=modified_since)
        items = items[offset or 0:]
        if limit is not None:
            items = items[:limit]
        return [skills_models.SkillSummary(**s.model_dump(include={"id", "name", "description", "last_modified"})) for s in items]

    async def get_skill(
        self: "DirectorySkillsAdapter",
        skill_id: str,
        modified_since: str | None = None,
    ) -> skills_models.Skill | None:
        skill = NamedObject.find_by_id(self._skills, skill_id)
        if skill is None or modified_since is None:
            return skill
        return skills_models.Skill.find(skill, modified_since=modified_since)
