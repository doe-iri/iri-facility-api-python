"""Generic skills adapter driven by a JSON manifest.

    {"skills": [
      {"name": "my-skill",
       "files": {"SKILL.md": "my-skill/SKILL.md", "scripts/run.py": "/opt/run.py"}},
      {"name": "other-skill", "type": "archive", "description": "...",
       "url": "https://example.org/other-skill.tar.gz", "digest": "sha256:..."}
    ]}

An entry with `files` is hosted by this API: keys are published paths, values are source
files (absolute or relative to the manifest). An entry with `url` is returned as given and
never fetched. Bytes are read once at startup, so a digest always matches what is served.
Invalid input raises, stopping startup, rather than publishing a partial set of skills.

Configure with `IRI_API_ADAPTER_skills=app.routers.skills.manifest_adapter.ManifestSkillsAdapter`
and `IRI_SKILLS_MANIFEST=/path/to/skills.json`. Subclasses may pass `manifest_path` instead.
"""
import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ...apilogger import get_stream_logger
from . import models as skills_models
from .facility_adapter import SkillsAdapter

LOGGER = get_stream_logger(__name__)

_HOSTED_ENTRY_KEYS = {"name", "description", "files"}


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: list[dict[str, Any]]


def frontmatter_value(text: str, key: str) -> str | None:
    """Return a top-level `key: value` line from the SKILL.md frontmatter, or None.

    Not a YAML parser: SKILL.md is served as-is, only name/description are surfaced for the index.
    """
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith(f"{key}:"):
            return line[len(key) + 1:].strip().strip("'\"") or None
    return None


def _digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _check_published_path(path: str) -> None:
    # Serving is an exact lookup, so this cannot reach the server's filesystem. It protects
    # clients, which write each published path to disk when they reconstruct a skill.
    if "\\" in path or any(part in ("", ".", "..") for part in path.split("/")):
        raise ValueError(f"published path {path!r} must be relative, using '/' with no empty, '.' or '..' segments")


def _description(entry: dict[str, Any], skill_md: str) -> str | None:
    if entry.get("description"):
        return entry["description"]
    description = frontmatter_value(skill_md, "description")
    if description and description[0] in (">", "|"):
        raise ValueError("SKILL.md description is a YAML block scalar; make it a single line or set 'description' in the manifest")
    return description


class ManifestSkillsAdapter(SkillsAdapter):
    """Publish exactly the skills and files named by a JSON manifest."""

    def __init__(self, manifest_path: str | os.PathLike | None = None):
        path = manifest_path if manifest_path is not None else os.environ.get("IRI_SKILLS_MANIFEST")
        if not path:
            raise ValueError("IRI_SKILLS_MANIFEST is not set; it must name the skills manifest for ManifestSkillsAdapter")
        self._skills: list[skills_models.Skill] = []
        self._contents: dict[tuple[str, str], bytes] = {}
        self._load(Path(path))
        LOGGER.info("Loaded %d skill(s) from %s: %s", len(self._skills), path, [s.name for s in self._skills])

    def _load(self, manifest_path: Path) -> None:
        try:
            manifest = _Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        except ValidationError as exc:
            raise ValueError(f"Invalid skills manifest {manifest_path}: {exc}") from exc
        names = set()
        for entry in manifest.skills:
            try:
                skill = self._load_entry(entry, manifest_path.parent)
                if skill.name in names:
                    raise ValueError("duplicate skill name")
            except (OSError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid skills manifest {manifest_path}, skill {entry.get('name')!r}: {exc}") from exc
            names.add(skill.name)
            self._skills.append(skill)

    def _load_entry(self, entry: dict[str, Any], base_dir: Path) -> skills_models.Skill:
        if ("files" in entry) == ("url" in entry):
            raise ValueError("an entry must have exactly one of 'files' or 'url'")
        if "url" in entry:
            return skills_models.Skill.model_validate(entry)
        unexpected = entry.keys() - _HOSTED_ENTRY_KEYS
        if unexpected:
            raise ValueError(f"an entry with 'files' cannot also set {sorted(unexpected)}; its type and digest are derived")
        return self._load_hosted(entry, base_dir)

    def _load_hosted(self, entry: dict[str, Any], base_dir: Path) -> skills_models.Skill:
        name, sources = entry.get("name"), entry["files"]
        if not isinstance(sources, dict) or skills_models.SKILL_FILE_NAME not in sources:
            raise ValueError(f"'files' must map published paths to source files and include {skills_models.SKILL_FILE_NAME}")

        files, contents = [], {}
        for path, source in sources.items():
            _check_published_path(path)
            source_path = base_dir / source
            data = source_path.read_bytes()
            contents[(name, path)] = data
            executable = bool(source_path.stat().st_mode & stat.S_IXUSR)
            files.append(skills_models.SkillFile(skill_name=name, path=path, digest=_digest(data), executable=executable))
        files.sort(key=lambda f: (f.path != skills_models.SKILL_FILE_NAME, f.path))

        skill_md_bytes = contents[(name, skills_models.SKILL_FILE_NAME)]
        skill_md = skill_md_bytes.decode("utf-8")
        frontmatter_name = frontmatter_value(skill_md, "name")
        if frontmatter_name != name:
            raise ValueError(f"SKILL.md frontmatter name {frontmatter_name!r} does not match the manifest")
        skill = skills_models.Skill(name=name, description=_description(entry, skill_md), digest=_digest(skill_md_bytes), files=files)
        self._contents.update(contents)
        return skill

    async def get_skills(self: "ManifestSkillsAdapter") -> list[skills_models.Skill]:
        return self._skills

    async def get_skill_file(self: "ManifestSkillsAdapter", name: str, path: str) -> bytes | None:
        return self._contents.get((name, path))
