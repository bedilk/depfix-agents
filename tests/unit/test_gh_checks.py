"""Unit tests for :mod:`depfix.gh.checks`."""

from __future__ import annotations

import httpx
import respx

from depfix.gh.checks import annotations_from_scan, create_check_run
from depfix.scanners.models import (
    CallSite,
    CallSiteKind,
    MatchConfidence,
    RepoScanResult,
)

_BASE = "https://api.github.example"


def _scan_result(sites: list[CallSite]) -> RepoScanResult:
    return RepoScanResult(
        repo_full_name="acme/app",
        commit_sha="abc123",
        files_scanned=10,
        call_sites=sites,
        dependencies=[],
    )


def _site(
    filepath: str = "src/index.ts",
    line: int = 42,
    confidence: MatchConfidence = MatchConfidence.HIGH,
    kind: CallSiteKind = CallSiteKind.METHOD_CALL,
    symbol: str = "openai.createModeration",
    evidence: str = "removed in v4",
) -> CallSite:
    return CallSite(
        filepath=filepath,
        line_number=line,
        column=0,
        line_content="createModeration()",
        kind=kind,
        confidence=confidence,
        symbol=symbol,
        evidence=evidence,
    )


def test_annotations_from_scan_maps_call_sites() -> None:
    result = _scan_result([_site(), _site(line=100, confidence=MatchConfidence.LOW)])
    annotations = annotations_from_scan(result, [])

    assert len(annotations) == 2
    assert annotations[0]["path"] == "src/index.ts"
    assert annotations[0]["start_line"] == 42
    assert annotations[0]["annotation_level"] == "warning"
    assert "openai.createModeration" in annotations[0]["message"]

    assert annotations[1]["annotation_level"] == "notice"


def test_annotations_from_scan_empty_when_no_sites() -> None:
    result = _scan_result([])
    assert annotations_from_scan(result, []) == []


@respx.mock(base_url=_BASE)
def test_create_check_run_posts_annotations(respx_mock: respx.Router) -> None:
    route = respx_mock.post("/repos/acme/app/check-runs").mock(
        return_value=httpx.Response(
            201,
            json={"id": 123, "name": "depfix scan", "status": "completed"},
        )
    )

    result = create_check_run(
        owner="acme",
        repo="app",
        name="depfix scan",
        head_sha="abc123",
        token="ghs_token",
        title="depfix: 2 findings",
        summary="Found 2 actionable call sites.",
        annotations=[
            {
                "path": "src/index.ts",
                "start_line": 42,
                "end_line": 42,
                "annotation_level": "warning",
                "message": "test",
                "title": "depfix: method_call",
            }
        ],
        api_url=_BASE,
    )

    assert route.called
    assert result["id"] == 123


@respx.mock(base_url=_BASE)
def test_create_check_run_batches_over_50(respx_mock: respx.Router) -> None:
    create_route = respx_mock.post("/repos/acme/app/check-runs").mock(
        return_value=httpx.Response(201, json={"id": 456, "name": "test", "status": "completed"})
    )
    patch_route = respx_mock.patch("/repos/acme/app/check-runs/456").mock(
        return_value=httpx.Response(200, json={"id": 456})
    )

    annotations = [
        {
            "path": f"file{i}.ts",
            "start_line": i,
            "end_line": i,
            "annotation_level": "warning",
            "message": f"finding {i}",
            "title": "test",
        }
        for i in range(75)
    ]

    create_check_run(
        owner="acme",
        repo="app",
        name="test",
        head_sha="abc123",
        token="ghs_token",
        annotations=annotations,
        api_url=_BASE,
    )

    assert create_route.called
    assert patch_route.called
