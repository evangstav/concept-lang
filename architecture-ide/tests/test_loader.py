"""Tests for concept_lang.loader (P3 workspace loader)."""

from pathlib import Path

import pytest

from concept_lang.ast import Workspace
from concept_lang.loader import load_workspace
from concept_lang.validate.diagnostic import Diagnostic


FIXTURES_ROOT = Path(__file__).parent / "fixtures"


class TestLoadWorkspaceHappyPath:
    def test_architecture_ide_workspace_loads_all_files(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "architecture_ide")
        assert isinstance(ws, Workspace)
        assert diags == []
        assert set(ws.concepts.keys()) == {
            "Concept",
            "DesignSession",
            "Diagram",
            "Workspace",
        }
        assert set(ws.syncs.keys()) == {
            "SessionIntroduces",
            "SpecifyDrawsDiagram",
            "WorkspaceTracksConcept",
        }

    def test_architecture_ide_counts(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "architecture_ide")
        assert diags == []
        assert len(ws.concepts) == 4
        assert len(ws.syncs) == 3

    def test_realworld_workspace_loads_all_files(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "realworld")
        assert isinstance(ws, Workspace)
        assert diags == []
        assert set(ws.concepts.keys()) == {
            "Article",
            "JWT",
            "Password",
            "Profile",
            "User",
            "Web",
        }
        assert set(ws.syncs.keys()) == {
            "FormatArticle",
            "NewUserToken",
            "RegisterDefaultProfile",
            "RegisterError",
            "RegisterSetPassword",
            "RegisterUser",
        }

    def test_realworld_counts(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "realworld")
        assert diags == []
        assert len(ws.concepts) == 6
        assert len(ws.syncs) == 6

    def test_concepts_keyed_by_concept_name_not_file_stem(self):
        ws, _ = load_workspace(FIXTURES_ROOT / "architecture_ide")
        # Concept AST is keyed by its declared name, not the filename.
        counter = ws.concepts["Concept"]
        assert counter.name == "Concept"
        assert counter.line == 1  # `concept Concept ...` on line 1

    def test_syncs_keyed_by_sync_name_not_file_stem(self):
        ws, _ = load_workspace(FIXTURES_ROOT / "architecture_ide")
        # File is `session_introduces.sync` but the sync name is SessionIntroduces.
        s = ws.syncs["SessionIntroduces"]
        assert s.name == "SessionIntroduces"
        assert s.line == 1  # `sync SessionIntroduces` on line 1

    def test_nested_subdirectories_supported_for_concepts(self, tmp_path):
        # rglob must descend into arbitrary subtrees.
        nested = tmp_path / "concepts" / "auth" / "deep"
        nested.mkdir(parents=True)
        (nested / "Tiny.concept").write_text(
            (
                "concept Tiny\n"
                "\n"
                "  purpose\n"
                "    tiny thing\n"
                "\n"
                "  actions\n"
                "    noop [ ] => [ ok: boolean ]\n"
                "      do nothing\n"
                "\n"
                "  operational principle\n"
                "    after noop [ ] => [ ok: true ]\n"
            ),
            encoding="utf-8",
        )
        ws, diags = load_workspace(tmp_path)
        assert diags == []
        assert "Tiny" in ws.concepts

    def test_nested_subdirectories_supported_for_syncs(self, tmp_path):
        nested = tmp_path / "syncs" / "group" / "sub"
        nested.mkdir(parents=True)
        (nested / "x.sync").write_text(
            "sync DeepSync\n\n  when\n    A/do: [ ] => [ ]\n  then\n    B/do: [ ] => [ ]\n",
            encoding="utf-8",
        )
        ws, diags = load_workspace(tmp_path)
        assert diags == []
        assert "DeepSync" in ws.syncs
