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


class TestLoadWorkspaceErrors:
    def test_bad_concept_still_loads_the_good_ones(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "negative" / "loader" / "bad_concept")
        # Counter parses fine, Broken does not.
        assert "Counter" in ws.concepts
        assert "Broken" not in ws.concepts
        # The sync still loads because the broken concept did not short-circuit us.
        assert "LogInc" in ws.syncs
        # One P0 diagnostic for Broken.concept.
        p0s = [d for d in diags if d.code == "P0"]
        assert len(p0s) == 1
        assert p0s[0].severity == "error"
        assert p0s[0].file is not None
        assert p0s[0].file.name == "Broken.concept"
        # Line is surfaced from the Lark exception (best-effort).
        assert p0s[0].line is not None

    def test_empty_workspace_has_no_diagnostics(self):
        ws, diags = load_workspace(FIXTURES_ROOT / "negative" / "loader" / "empty")
        assert ws.concepts == {}
        assert ws.syncs == {}
        assert diags == []

    def test_missing_root_returns_l0_diagnostic(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        ws, diags = load_workspace(missing)
        assert ws.concepts == {}
        assert ws.syncs == {}
        assert len(diags) == 1
        assert diags[0].code == "L0"
        assert diags[0].severity == "error"
        assert diags[0].file == missing

    def test_missing_concepts_dir_is_ok(self, tmp_path):
        # Root exists, syncs/ exists, concepts/ does not — that's a valid
        # "syncs only" workspace and should not produce a diagnostic.
        (tmp_path / "syncs").mkdir()
        (tmp_path / "syncs" / "x.sync").write_text(
            "sync X\n\n  when\n    A/do: [ ] => [ ]\n  then\n    B/do: [ ] => [ ]\n",
            encoding="utf-8",
        )
        ws, diags = load_workspace(tmp_path)
        assert ws.concepts == {}
        assert "X" in ws.syncs
        assert diags == []

    def test_missing_syncs_dir_is_ok(self, tmp_path):
        (tmp_path / "concepts").mkdir()
        (tmp_path / "concepts" / "Tiny.concept").write_text(
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
        assert "Tiny" in ws.concepts
        assert ws.syncs == {}
        assert diags == []

    def test_broken_sync_produces_p0_and_does_not_hide_concept(self, tmp_path):
        (tmp_path / "concepts").mkdir()
        (tmp_path / "concepts" / "Counter.concept").write_text(
            (
                "concept Counter\n"
                "\n"
                "  purpose\n"
                "    count things\n"
                "\n"
                "  state\n"
                "    total: int\n"
                "\n"
                "  actions\n"
                "    inc [ ] => [ total: int ]\n"
                "      add one to total\n"
                "\n"
                "  operational principle\n"
                "    after inc [ ] => [ total: 1 ]\n"
            ),
            encoding="utf-8",
        )
        (tmp_path / "syncs").mkdir()
        (tmp_path / "syncs" / "broken.sync").write_text(
            "sync Broken\n  this is nonsense\n",
            encoding="utf-8",
        )
        ws, diags = load_workspace(tmp_path)
        assert "Counter" in ws.concepts
        assert ws.syncs == {}
        assert len(diags) == 1
        assert diags[0].code == "P0"
        assert diags[0].file is not None
        assert diags[0].file.name == "broken.sync"
        assert diags[0].line is not None

    def test_empty_root_directory_is_clean(self, tmp_path):
        # Root exists but contains neither concepts/ nor syncs/.
        ws, diags = load_workspace(tmp_path)
        assert ws.concepts == {}
        assert ws.syncs == {}
        assert diags == []


class TestLoadAndValidateIntegration:
    """
    End-to-end pin: loading a positive-fixture workspace and validating
    the result must produce zero error-level diagnostics.
    """

    def test_load_and_validate_realworld_is_clean(self):
        from concept_lang.parse import parse_sync_file
        from concept_lang.validate import validate_workspace

        realworld = Path(__file__).parent / "fixtures" / "realworld"
        ws, load_diags = load_workspace(realworld)
        assert load_diags == [], (
            "loading realworld produced parse diagnostics:\n"
            + "\n".join(f"  {d.code} ({d.file}): {d.message}" for d in load_diags)
        )
        assert ws.concepts
        assert ws.syncs

        # Build the concept_files / sync_files map so that validator
        # diagnostics carry real paths.
        concept_files = {
            name: (realworld / "concepts" / f"{name}.concept")
            for name in ws.concepts
        }
        sync_files: dict = {}
        for p in sorted((realworld / "syncs").glob("*.sync")):
            sync_files[parse_sync_file(p).name] = p

        validate_diags = validate_workspace(
            ws, concept_files=concept_files, sync_files=sync_files
        )
        errors = [d for d in validate_diags if d.severity == "error"]
        assert errors == [], (
            "realworld validator errors after load_workspace:\n"
            + "\n".join(f"  {d.code} ({d.file}): {d.message}" for d in errors)
        )

    def test_load_and_validate_architecture_ide_is_clean(self):
        from concept_lang.parse import parse_sync_file
        from concept_lang.validate import validate_workspace

        root = Path(__file__).parent / "fixtures" / "architecture_ide"
        ws, load_diags = load_workspace(root)
        assert load_diags == []

        concept_files = {
            name: (root / "concepts" / f"{name}.concept")
            for name in ws.concepts
        }
        sync_files: dict = {}
        for p in sorted((root / "syncs").glob("*.sync")):
            sync_files[parse_sync_file(p).name] = p

        validate_diags = validate_workspace(
            ws, concept_files=concept_files, sync_files=sync_files
        )
        errors = [d for d in validate_diags if d.severity == "error"]
        assert errors == []


class TestLoaderReexport:
    def test_load_workspace_importable_from_package_root(self):
        # Public API: MCP tools in P4 import from the package root.
        from concept_lang import load_workspace as top_level
        from concept_lang.loader import load_workspace as module_level
        assert top_level is module_level


class TestP3Gate:
    """
    The P3 gate: the full P1+P2+P3 pipeline must accept both positive
    fixture workspaces, produce no parse errors, and carry real source
    positions through every positioned AST node.
    """

    def test_positive_fixtures_round_trip_through_loader_with_positions(self):
        for subdir in ("architecture_ide", "realworld"):
            root = Path(__file__).parent / "fixtures" / subdir
            ws, diags = load_workspace(root)
            assert diags == [], (
                f"{subdir}: parse diagnostics: "
                + "; ".join(f"{d.code} {d.file}: {d.message}" for d in diags)
            )
            assert ws.concepts, f"{subdir}: no concepts loaded"
            # Every loaded concept must carry real line numbers on the
            # nodes the transformer sets (ConceptAST.line is the most
            # reliable — it's always the first token of the file).
            for name, concept in ws.concepts.items():
                assert concept.line is not None, f"{subdir}/{name}: no ConceptAST.line"
                assert concept.line >= 1
                # State declarations, when present, also carry lines.
                for decl in concept.state:
                    assert decl.line is not None, (
                        f"{subdir}/{name}: state '{decl.name}' has no line"
                    )
            for name, sync in ws.syncs.items():
                assert sync.line is not None, f"{subdir}/{name}: no SyncAST.line"
                for ap in sync.when:
                    assert ap.line is not None, (
                        f"{subdir}/{name}: when pattern has no line"
                    )
                for ap in sync.then:
                    assert ap.line is not None, (
                        f"{subdir}/{name}: then pattern has no line"
                    )
