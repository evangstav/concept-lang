"""Pin the scaffold_concepts tool's embedded methodology block (P5)."""

from __future__ import annotations

import re

from concept_lang.tools.scaffold_tools import _METHODOLOGY


class TestScaffoldMethodologyIsV2:
    def test_teaches_named_io(self):
        assert "[ <in1>: <T1>" in _METHODOLOGY or "[ <in1>:" in _METHODOLOGY, (
            "scaffold methodology must teach named input/output signatures"
        )

    def test_teaches_multi_case_actions(self):
        assert "success case" in _METHODOLOGY.lower()
        assert "error case" in _METHODOLOGY.lower()

    def test_teaches_operational_principle_section(self):
        assert "operational principle" in _METHODOLOGY.lower()

    def test_teaches_top_level_syncs(self):
        assert ".sync" in _METHODOLOGY
        assert re.search(r"sync\s+<SyncName>", _METHODOLOGY), (
            "scaffold methodology must teach the top-level sync file shape"
        )

    def test_no_v1_sync_section_inside_concept(self):
        # The v1 teaching block had a `sync` section as part of the concept.
        # The new block explicitly says syncs are separate files.
        body = _METHODOLOGY
        # Forbid "sync" as a section header inside the concept block —
        # `      sync\n` with exactly the concept indent.
        assert not re.search(r"(?m)^      sync\s*$", body), (
            "scaffold methodology still has a v1-style inline `sync` section"
        )

    def test_no_v1_prepost_keywords(self):
        assert "pre:" not in _METHODOLOGY
        assert "post:" not in _METHODOLOGY

    def test_explicit_independence_rule(self):
        assert "INDEPENDENT" in _METHODOLOGY or "independent" in _METHODOLOGY
