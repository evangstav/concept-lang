"""
Docs-lint contract tests (concept-lang 0.2.0 — P6).

These tests enforce a contract between the user-facing documentation
(`README.md`, `CHANGELOG.md`, `docs/methodology.md`) and the 0.2.0
paper-alignment release:

  1. README lists all five skills and contains a v2 concept code block.
  2. README does not contain v1 `pre:` / `post:` keywords inside a
     fenced code block tagged `concept`. Lines inside a fenced block
     tagged `legacy` are exempt so a migration guide can show a
     before/after.
  3. methodology.md cites the paper via the arXiv URL and references
     the Counter + Logger example.
  4. CHANGELOG.md has a `## [0.2.0]` header, an `## [Unreleased]`
     placeholder, and a paper reference. The CHANGELOG's migration
     section contains a `legacy` fenced block showing the v1 → v2
     before/after; that block is exempt from the forbidden-phrase
     check via `_strip_legacy_fences`.

The test file is deliberately small. It complements tests/test_skills.py
(skill-lint) but does NOT import from it — the two surfaces have
different failure modes and should fail independently.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
METHODOLOGY = REPO_ROOT / "docs" / "methodology.md"


FIVE_SKILLS = ("build", "build-sync", "review", "scaffold", "explore")

PAPER_URL = "arxiv.org/abs/2508.14511"


def _strip_legacy_fences(text: str) -> str:
    """Remove the contents of any fenced block tagged `legacy`.

    Decision (N): the legacy carve-out lets the README and CHANGELOG
    show a v1 → v2 migration snippet without tripping the
    forbidden-phrase check. No other fence tag is exempt.
    """
    out_lines: list[str] = []
    in_legacy = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```legacy"):
            in_legacy = True
            continue
        if in_legacy and stripped == "```":
            in_legacy = False
            continue
        if not in_legacy:
            out_lines.append(line)
    return "\n".join(out_lines)


def _concept_fence_bodies(text: str) -> list[str]:
    """Return the body text of every fenced block tagged `concept`."""
    pattern = re.compile(r"^```concept\s*\n(.*?)\n```", re.MULTILINE | re.DOTALL)
    return pattern.findall(text)


def test_readme_exists_and_is_non_empty() -> None:
    assert README.exists(), f"README missing: {README}"
    assert README.read_text().strip(), "README is empty"


def test_readme_lists_all_five_skills() -> None:
    text = README.read_text()
    missing = [s for s in FIVE_SKILLS if f"`{s}`" not in text and f"**{s}**" not in text]
    assert not missing, f"README is missing skills: {missing}"


def test_readme_has_v2_concept_code_block() -> None:
    text = README.read_text()
    bodies = _concept_fence_bodies(text)
    assert bodies, "README has no fenced `concept` code block"
    # At least one body must use the v2 structure: `purpose`, `state`,
    # `actions`, `operational principle`.
    for body in bodies:
        if (
            "purpose" in body
            and "state" in body
            and "actions" in body
            and "operational principle" in body
        ):
            return
    pytest.fail(
        "README has concept fences but none use the v2 structure "
        "(purpose / state / actions / operational principle)"
    )


def test_readme_has_no_v1_pre_post_keywords() -> None:
    text = _strip_legacy_fences(README.read_text())
    bodies = _concept_fence_bodies(text)
    for body in bodies:
        assert not re.search(r"(?m)^\s*pre\s*:", body), (
            "README concept fence contains v1 `pre:` keyword"
        )
        assert not re.search(r"(?m)^\s*post\s*:", body), (
            "README concept fence contains v1 `post:` keyword"
        )


def test_readme_cites_paper() -> None:
    text = README.read_text()
    assert PAPER_URL in text, f"README does not cite {PAPER_URL}"


def test_methodology_exists_and_is_non_empty() -> None:
    assert METHODOLOGY.exists(), f"methodology.md missing: {METHODOLOGY}"
    assert METHODOLOGY.read_text().strip(), "methodology.md is empty"


def test_methodology_cites_paper() -> None:
    text = METHODOLOGY.read_text()
    assert PAPER_URL in text, f"methodology.md does not cite {PAPER_URL}"


def test_methodology_walks_counter_and_logger() -> None:
    text = METHODOLOGY.read_text()
    assert "Counter" in text, "methodology.md does not mention Counter"
    assert "Logger" in text, "methodology.md does not mention Logger"
    assert "LogInc" in text or "log" in text.lower(), (
        "methodology.md does not reference the log sync"
    )


def test_changelog_exists_and_is_non_empty() -> None:
    assert CHANGELOG.exists(), f"CHANGELOG.md missing: {CHANGELOG}"
    assert CHANGELOG.read_text().strip(), "CHANGELOG.md is empty"


def test_changelog_has_0_2_0_entry() -> None:
    text = CHANGELOG.read_text()
    assert re.search(r"^## \[0\.2\.0\]", text, re.MULTILINE), (
        "CHANGELOG.md does not have a `## [0.2.0]` section header"
    )


def test_changelog_cites_paper() -> None:
    text = CHANGELOG.read_text()
    assert PAPER_URL in text, f"CHANGELOG.md does not cite {PAPER_URL}"


def test_changelog_has_unreleased_placeholder() -> None:
    text = CHANGELOG.read_text()
    assert re.search(r"^## \[Unreleased\]", text, re.MULTILINE), (
        "CHANGELOG.md does not have a `## [Unreleased]` placeholder section"
    )


def test_changelog_has_no_v1_pre_post_keywords_outside_legacy_fence() -> None:
    """Defensive check: the CHANGELOG's migration section contains a
    ``legacy`` fenced block with v1 ``pre:`` / ``post:`` syntax. After
    stripping the legacy fence, no v1 keywords should survive anywhere
    in the file — not in concept fences, not in prose.
    """
    text = _strip_legacy_fences(CHANGELOG.read_text())
    assert not re.search(r"(?m)^\s*pre\s*:", text), (
        "CHANGELOG.md contains v1 `pre:` keyword outside a legacy fence"
    )
    assert not re.search(r"(?m)^\s*post\s*:", text), (
        "CHANGELOG.md contains v1 `post:` keyword outside a legacy fence"
    )
