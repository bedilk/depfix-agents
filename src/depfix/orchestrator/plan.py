"""Serializable, immutable output of a verified ``depfix plan`` run."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from depfix.core.pipeline import FixPipelineResult


@dataclass(frozen=True)
class PlannedEdit:
    relpath: str
    original_content: str
    fixed_content: str
    diff: str
    confidence: float
    usages_fixed: int


@dataclass(frozen=True)
class PlanArtifact:
    repo_full_name: str
    base_sha: str
    change_dedupe_key: str
    edits: tuple[PlannedEdit, ...]

    @classmethod
    def from_result(cls, repo: str, base_sha: str, result: FixPipelineResult) -> PlanArtifact:
        return cls(
            repo_full_name=repo,
            base_sha=base_sha,
            change_dedupe_key=result.breaking_change.dedupe_key,
            edits=tuple(
                PlannedEdit(e.relpath, e.original_content, e.fixed_content, e.diff, e.confidence, e.usages_fixed)
                for e in result.edits
                if e.verdict.value == "kept"
            ),
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "version": 1, "repo_full_name": self.repo_full_name, "base_sha": self.base_sha,
            "change_dedupe_key": self.change_dedupe_key,
            "edits": [e.__dict__ for e in self.edits],
        }, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def read(cls, path: str | Path) -> PlanArtifact:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("version") != 1:
            raise ValueError("unsupported plan artifact version")
        return cls(raw["repo_full_name"], raw["base_sha"], raw["change_dedupe_key"], tuple(PlannedEdit(**e) for e in raw["edits"]))
