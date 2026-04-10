"""Tests for the new validator (concept_lang.validate)."""

from pathlib import Path

from concept_lang.validate.diagnostic import Diagnostic


class TestDiagnostic:
    def test_round_trip(self):
        d = Diagnostic(
            severity="error",
            file=Path("tests/fixtures/negative/C1_state_references_other_concept.concept"),
            line=5,
            column=3,
            code="C1",
            message="state field 'owner' references unknown type 'User'",
        )
        dumped = d.model_dump(mode="json")
        restored = Diagnostic.model_validate(dumped)
        assert restored == d

    def test_workspace_scoped_has_no_file(self):
        d = Diagnostic(
            severity="warning",
            file=None,
            line=None,
            column=None,
            code="S5",
            message="sync references only one concept",
        )
        assert d.file is None
        assert d.line is None

    def test_severity_literal(self):
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Diagnostic(
                severity="fatal",  # type: ignore[arg-type]
                file=None,
                line=None,
                column=None,
                code="C1",
                message="...",
            )
