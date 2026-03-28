"""Smoke tests for Phase 08 pipeline data cleanup.

Verifies:
- FOUND-02: No FTS5 virtual table references exist in grantflow/ Python code
- QUAL-06: sbir.py does not import the dead validate_award_amounts symbol
"""

from pathlib import Path


GRANTFLOW_SRC = Path(__file__).parent.parent / "grantflow"

# Patterns that would indicate leftover FTS5/virtual-table references
_FTS5_PATTERNS = (
    "fts5",
    "FTS5",
    "_fts",
    "virtual table",
    "VIRTUAL TABLE",
)


class TestFts5Absence:
    def test_no_fts5_references(self):
        """No .py file under grantflow/ may reference FTS5 virtual tables."""
        matches: list[str] = []
        for py_file in GRANTFLOW_SRC.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for pattern in _FTS5_PATTERNS:
                if pattern in text:
                    matches.append(
                        f"{py_file.relative_to(GRANTFLOW_SRC.parent)}: '{pattern}'"
                    )

        assert matches == [], (
            "FTS5 virtual table references found in grantflow/ source:\n"
            + "\n".join(matches)
        )


class TestSbirDeadImport:
    def test_sbir_no_dead_import(self):
        """sbir.py must not import validate_award_amounts (SBIR has no floor/ceiling fields)."""
        sbir_path = GRANTFLOW_SRC / "ingest" / "sbir.py"
        assert sbir_path.exists(), f"sbir.py not found at {sbir_path}"
        content = sbir_path.read_text(encoding="utf-8")
        assert "validate_award_amounts" not in content, (
            "sbir.py still imports validate_award_amounts — dead import must be removed"
        )
