"""Unit tests for grantflow.dedup — canonical ID generation and duplicate detection."""

import pytest
from unittest.mock import MagicMock, patch

from grantflow.dedup import make_canonical_id, find_duplicate_groups, assign_canonical_ids


# ─── make_canonical_id ─────────────────────────────────────────────────────────

class TestMakeCanonicalId:
    def test_returns_string_with_canon_prefix(self):
        result = make_canonical_id({"opportunity_number": "DE-FOA-0002345"})
        assert isinstance(result, str)
        assert result.startswith("canon_")

    def test_returns_16_char_hex_after_prefix(self):
        result = make_canonical_id({"opportunity_number": "DE-FOA-0002345"})
        hex_part = result[len("canon_"):]
        assert len(hex_part) == 16
        # must be valid hex
        int(hex_part, 16)

    def test_same_opportunity_number_same_canonical_id(self):
        r1 = {"opportunity_number": "DE-FOA-0002345"}
        r2 = {"opportunity_number": "DE-FOA-0002345"}
        assert make_canonical_id(r1) == make_canonical_id(r2)

    def test_trailing_whitespace_normalized(self):
        r1 = {"opportunity_number": "DE-FOA-0002345 "}
        r2 = {"opportunity_number": "DE-FOA-0002345"}
        assert make_canonical_id(r1) == make_canonical_id(r2)

    def test_leading_whitespace_normalized(self):
        r1 = {"opportunity_number": "  DE-FOA-0002345"}
        r2 = {"opportunity_number": "DE-FOA-0002345"}
        assert make_canonical_id(r1) == make_canonical_id(r2)

    def test_case_insensitive_opportunity_number(self):
        r1 = {"opportunity_number": "de-foa-0002345"}
        r2 = {"opportunity_number": "DE-FOA-0002345"}
        assert make_canonical_id(r1) == make_canonical_id(r2)

    def test_different_opportunity_numbers_different_canonical_ids(self):
        r1 = {"opportunity_number": "DE-FOA-0001"}
        r2 = {"opportunity_number": "DE-FOA-0002"}
        assert make_canonical_id(r1) != make_canonical_id(r2)

    def test_deterministic_same_input_same_output(self):
        record = {"opportunity_number": "DE-FOA-0002345"}
        result1 = make_canonical_id(record)
        result2 = make_canonical_id(record)
        assert result1 == result2

    def test_fallback_to_cfda_agency_close_date(self):
        r1 = {
            "opportunity_number": None,
            "cfda_numbers": "81.049",
            "agency_code": "DOE",
            "close_date": "2024-06-30",
        }
        r2 = {
            "opportunity_number": None,
            "cfda_numbers": "81.049",
            "agency_code": "DOE",
            "close_date": "2024-06-30",
        }
        assert make_canonical_id(r1) == make_canonical_id(r2)

    def test_fallback_empty_string_opportunity_number(self):
        r1 = {
            "opportunity_number": "",
            "cfda_numbers": "81.049",
            "agency_code": "DOE",
            "close_date": "2024-06-30",
        }
        r2 = {
            "opportunity_number": None,
            "cfda_numbers": "81.049",
            "agency_code": "DOE",
            "close_date": "2024-06-30",
        }
        assert make_canonical_id(r1) == make_canonical_id(r2)

    def test_fallback_different_cfda_different_canonical_id(self):
        r1 = {
            "opportunity_number": None,
            "cfda_numbers": "81.049",
            "agency_code": "DOE",
            "close_date": "2024-06-30",
        }
        r2 = {
            "opportunity_number": None,
            "cfda_numbers": "93.001",
            "agency_code": "DOE",
            "close_date": "2024-06-30",
        }
        assert make_canonical_id(r1) != make_canonical_id(r2)

    def test_fallback_none_fields_treated_as_empty(self):
        r1 = {
            "opportunity_number": None,
            "cfda_numbers": None,
            "agency_code": None,
            "close_date": None,
        }
        r2 = {
            "opportunity_number": None,
            "cfda_numbers": "",
            "agency_code": "",
            "close_date": "",
        }
        assert make_canonical_id(r1) == make_canonical_id(r2)

    def test_opportunity_number_takes_priority_over_fallback(self):
        r1 = {
            "opportunity_number": "DE-FOA-0001",
            "cfda_numbers": "81.049",
            "agency_code": "DOE",
            "close_date": "2024-06-30",
        }
        r2 = {
            "opportunity_number": "DE-FOA-0001",
            "cfda_numbers": "99.999",  # different CFDA
            "agency_code": "NASA",     # different agency
            "close_date": "2025-01-01",  # different date
        }
        # Same opportunity_number → same canonical_id regardless of other fields
        assert make_canonical_id(r1) == make_canonical_id(r2)

    def test_missing_keys_handled_gracefully(self):
        # Dict with no keys at all — should not raise
        result = make_canonical_id({})
        assert isinstance(result, str)
        assert result.startswith("canon_")


# ─── find_duplicate_groups ─────────────────────────────────────────────────────

class TestFindDuplicateGroups:
    def test_returns_list(self):
        session = MagicMock()
        # Simulate no duplicate rows returned
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute.return_value = mock_result
        result = find_duplicate_groups(session)
        assert isinstance(result, list)

    def test_no_duplicates_returns_empty_list(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute.return_value = mock_result
        result = find_duplicate_groups(session)
        assert result == []

    def test_duplicates_returned_as_dicts(self):
        session = MagicMock()
        # Simulate one duplicate group
        row = MagicMock()
        row.canonical_id = "canon_abc123456789ab"
        row.count = 2
        row.ids = ["grants_gov_001", "sbir_001"]
        row.sources = ["grants_gov", "sbir"]
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([row]))
        session.execute.return_value = mock_result

        result = find_duplicate_groups(session)
        assert len(result) == 1
        g = result[0]
        assert g["canonical_id"] == "canon_abc123456789ab"
        assert g["count"] == 2
        assert isinstance(g["ids"], list)
        assert isinstance(g["sources"], list)

    def test_does_not_modify_data(self):
        """find_duplicate_groups must be read-only — no commits."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute.return_value = mock_result
        find_duplicate_groups(session)
        session.commit.assert_not_called()
        session.add.assert_not_called()


# ─── assign_canonical_ids ──────────────────────────────────────────────────────

class TestAssignCanonicalIds:
    def test_returns_dict_with_assigned_and_already_set(self):
        """assign_canonical_ids returns stats dict."""
        session = MagicMock()
        # Simulate no opportunities with NULL canonical_id
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.yield_per.return_value = iter([])
        session.query.return_value = mock_query

        result = assign_canonical_ids(session)
        assert isinstance(result, dict)
        assert "assigned" in result
        assert "already_set" in result

    def test_already_set_count_for_empty_null_query(self):
        """When no NULLs exist, assigned=0."""
        session = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.yield_per.return_value = iter([])
        session.query.return_value = mock_query

        result = assign_canonical_ids(session)
        assert result["assigned"] == 0
