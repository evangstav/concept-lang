"""
Runtime dogfood test (concept-lang 0.3.1).

This test loads the plugin's own example workspace at
`architecture-ide/.concepts/` and asserts it is a valid v2
workspace according to the P2 validator rule set.

It is the dogfooding check that makes sure the canonical runtime
example stays paper-aligned. If this test fails, a recent change
either broke the example workspace (e.g., a new concept was added
that references another concept's state) or broke the validator
(unlikely because the positive fixture tests would catch that).

The test deliberately does NOT import any fixture path helper.
It walks up from this file to find the package root and loads
`<package_root>/.concepts/concepts/` and
`<package_root>/.concepts/syncs/` directly so a future move of
the test fixtures does not affect this test.

Note: the hidden `.concepts/` convention was introduced in 0.3.1.
Prior versions kept the workspace files at
`architecture-ide/{concepts,syncs,apps}/` directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from concept_lang.loader import load_workspace
from concept_lang.validate import validate_workspace


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PACKAGE_ROOT / ".concepts"


EXPECTED_CONCEPTS = {"Concept", "DesignSession", "Diagram", "Workspace"}
EXPECTED_SYNCS = {
    "SessionIntroduces",
    "SpecifyDrawsDiagram",
    "WorkspaceTracksConcept",
}


def test_runtime_workspace_loads() -> None:
    """The runtime workspace parses without any P0 / L0 errors."""
    ws, diagnostics = load_workspace(WORKSPACE_ROOT)
    errors = [d for d in diagnostics if d.severity == "error"]
    assert errors == [], f"Runtime workspace failed to load: {errors}"


def test_runtime_concept_set_matches_expected() -> None:
    """The runtime workspace has exactly the expected four concepts."""
    ws, _ = load_workspace(WORKSPACE_ROOT)
    assert set(ws.concepts.keys()) == EXPECTED_CONCEPTS, (
        f"Unexpected runtime concept set: {sorted(ws.concepts.keys())}. "
        f"If you added or removed a concept, update EXPECTED_CONCEPTS."
    )


def test_runtime_sync_set_matches_expected() -> None:
    """The runtime workspace has exactly the expected three syncs."""
    ws, _ = load_workspace(WORKSPACE_ROOT)
    assert set(ws.syncs.keys()) == EXPECTED_SYNCS, (
        f"Unexpected runtime sync set: {sorted(ws.syncs.keys())}. "
        f"If you added or removed a sync, update EXPECTED_SYNCS."
    )


def test_runtime_workspace_validates_clean() -> None:
    """The runtime workspace produces zero error-level diagnostics."""
    ws, load_diagnostics = load_workspace(WORKSPACE_ROOT)
    validate_diagnostics = validate_workspace(ws)
    all_diagnostics = list(load_diagnostics) + list(validate_diagnostics)
    errors = [d for d in all_diagnostics if d.severity == "error"]
    assert errors == [], (
        "Runtime workspace has error-level diagnostics:\n"
        + "\n".join(
            f"  {d.code} {d.file}:{d.line}: {d.message}" for d in errors
        )
    )
