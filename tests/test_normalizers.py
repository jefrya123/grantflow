"""Unit tests for grantflow.normalizers — all normalization utility functions."""

import json

from grantflow.normalizers import (
    normalize_date,
    normalize_eligibility_codes,
    normalize_agency_name,
    validate_award_amounts,
    normalize_category,
    normalize_funding_instrument,
)


# ─── normalize_date ────────────────────────────────────────────────────────────

class TestNormalizeDate:
    def test_none_returns_none(self):
        assert normalize_date(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_date("") is None

    def test_whitespace_only_returns_none(self):
        assert normalize_date("   ") is None

    def test_mm_slash_dd_slash_yyyy(self):
        assert normalize_date("01/15/2024") == "2024-01-15"

    def test_mm_slash_dd_slash_yyyy_zero_padded(self):
        assert normalize_date("03/01/2023") == "2023-03-01"

    def test_mmddyyyy_compact(self):
        assert normalize_date("01152024") == "2024-01-15"

    def test_iso_passthrough(self):
        assert normalize_date("2024-01-15") == "2024-01-15"

    def test_yyyymmdd_compact(self):
        assert normalize_date("20240115") == "2024-01-15"

    def test_mon_dd_yyyy(self):
        assert normalize_date("Jan 15 2024") == "2024-01-15"

    def test_garbage_returns_none(self):
        assert normalize_date("garbage") is None

    def test_garbage_does_not_return_raw(self):
        # Stricter than the old _normalize_date — must return None, not the raw string
        result = normalize_date("not-a-date")
        assert result is None

    def test_partial_date_returns_none(self):
        assert normalize_date("2024-01") is None

    def test_strips_whitespace_before_parsing(self):
        assert normalize_date("  2024-01-15  ") == "2024-01-15"


# ─── validate_award_amounts ────────────────────────────────────────────────────

class TestValidateAwardAmounts:
    def test_both_none_returns_none_none(self):
        assert validate_award_amounts(None, None) == (None, None)

    def test_floor_negative_returns_none_none(self):
        assert validate_award_amounts(-1.0, 10000.0) == (None, None)

    def test_ceiling_negative_returns_none_none(self):
        assert validate_award_amounts(1000.0, -5000.0) == (None, None)

    def test_both_negative_returns_none_none(self):
        assert validate_award_amounts(-100.0, -500.0) == (None, None)

    def test_floor_greater_than_ceiling_returns_none_ceiling(self):
        assert validate_award_amounts(50000.0, 10000.0) == (None, 10000.0)

    def test_floor_equal_ceiling_returns_both(self):
        assert validate_award_amounts(10000.0, 10000.0) == (10000.0, 10000.0)

    def test_valid_range_returns_both(self):
        assert validate_award_amounts(1000.0, 50000.0) == (1000.0, 50000.0)

    def test_floor_only_returns_floor_none(self):
        assert validate_award_amounts(5000.0, None) == (5000.0, None)

    def test_ceiling_only_returns_none_ceiling(self):
        assert validate_award_amounts(None, 25000.0) == (None, 25000.0)

    def test_zero_floor_is_valid(self):
        assert validate_award_amounts(0.0, 10000.0) == (0.0, 10000.0)

    def test_floor_negative_zero_edge_case(self):
        # -0.0 is technically not negative, but validate should treat like 0
        # float(-0.0) < 0 is False in Python, so (0.0, ceiling) should be returned
        assert validate_award_amounts(-0.0, 5000.0) == (0.0, 5000.0)


# ─── normalize_eligibility_codes ───────────────────────────────────────────────

class TestNormalizeEligibilityCodes:
    def test_none_returns_empty_json_array(self):
        assert normalize_eligibility_codes(None) == "[]"

    def test_empty_string_returns_empty_json_array(self):
        assert normalize_eligibility_codes("") == "[]"

    def test_empty_list_returns_empty_json_array(self):
        assert normalize_eligibility_codes([]) == "[]"

    def test_json_string_of_codes(self):
        result = normalize_eligibility_codes('["12", "25"]')
        parsed = json.loads(result)
        assert "Nonprofits (other than higher education) with 501(c)(3) status" in parsed
        assert "Others (see agency eligibility text)" in parsed

    def test_list_of_codes(self):
        result = normalize_eligibility_codes(["23", "21"])
        parsed = json.loads(result)
        assert "Small businesses" in parsed
        assert "Individuals" in parsed

    def test_unknown_codes_kept_as_is(self):
        result = normalize_eligibility_codes(["99", "UNKNOWN_CODE"])
        parsed = json.loads(result)
        assert "Unrestricted" in parsed
        assert "UNKNOWN_CODE" in parsed

    def test_returns_json_string(self):
        result = normalize_eligibility_codes(["00"])
        # Must be a valid JSON string, not a list
        assert isinstance(result, str)
        json.loads(result)  # should not raise

    def test_all_known_codes_mapped(self):
        all_codes = ["00","01","02","04","05","06","07","08","11","12","13","20","21","22","23","25","99"]
        result = normalize_eligibility_codes(all_codes)
        parsed = json.loads(result)
        assert len(parsed) == 17
        # None of them should be raw numeric codes
        for entry in parsed:
            assert not entry.isdigit()

    def test_single_code_as_bare_string(self):
        # A bare string like "12" (not a JSON array) should be treated as a single code
        result = normalize_eligibility_codes("12")
        parsed = json.loads(result)
        assert "Nonprofits (other than higher education) with 501(c)(3) status" in parsed

    def test_code_00_state_governments(self):
        result = normalize_eligibility_codes(["00"])
        assert "State governments" in json.loads(result)

    def test_code_06_higher_ed(self):
        result = normalize_eligibility_codes(["06"])
        assert "Public and State controlled institutions of higher education" in json.loads(result)


# ─── normalize_agency_name ─────────────────────────────────────────────────────

class TestNormalizeAgencyName:
    def test_none_returns_none(self):
        assert normalize_agency_name(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_agency_name("") is None

    def test_whitespace_only_returns_none(self):
        assert normalize_agency_name("   ") is None

    def test_strips_leading_trailing_whitespace(self):
        assert normalize_agency_name("  National Science Foundation  ") == "National Science Foundation"

    def test_collapses_internal_spaces(self):
        assert normalize_agency_name("Department  of  Energy") == "Department of Energy"

    def test_hhs_abbreviation(self):
        assert normalize_agency_name("HHS") == "Department of Health and Human Services"

    def test_dept_dot_of_hhs(self):
        assert normalize_agency_name("Dept. of Health and Human Services") == "Department of Health and Human Services"

    def test_dept_no_dot_hhs(self):
        assert normalize_agency_name("Dept of Health and Human Services") == "Department of Health and Human Services"

    def test_doe_abbreviation(self):
        assert normalize_agency_name("DOE") == "Department of Energy"

    def test_dept_dot_energy(self):
        assert normalize_agency_name("Dept. of Energy") == "Department of Energy"

    def test_nsf_abbreviation(self):
        assert normalize_agency_name("NSF") == "National Science Foundation"

    def test_nih_abbreviation(self):
        assert normalize_agency_name("NIH") == "National Institutes of Health"

    def test_usda_abbreviation(self):
        assert normalize_agency_name("USDA") == "Department of Agriculture"

    def test_unknown_name_passthrough(self):
        # Unknown names should be returned as-is (normalized whitespace)
        result = normalize_agency_name("Some Unknown Agency")
        assert result == "Some Unknown Agency"

    def test_known_name_unchanged(self):
        # Already-canonical names should pass through unchanged
        assert normalize_agency_name("National Science Foundation") == "National Science Foundation"


# ─── normalize_date — timezone offset edge cases (QUAL-05) ────────────────────

class TestNormalizeDateTimezoneOffset:
    def test_normalize_date_iso_with_tz_offset(self):
        """ISO 8601 with timezone offset (SAM.gov format) must return date portion only."""
        assert normalize_date("2024-03-15T00:00:00-04:00") == "2024-03-15"

    def test_normalize_date_iso_with_utc_z(self):
        """ISO 8601 with Z suffix (UTC) must return date portion only (Python 3.11+)."""
        assert normalize_date("2024-03-15T00:00:00Z") == "2024-03-15"


# ─── normalize_category ────────────────────────────────────────────────────────

class TestNormalizeCategory:
    def test_d_returns_discretionary(self):
        assert normalize_category("D") == "Discretionary"

    def test_m_returns_mandatory(self):
        assert normalize_category("M") == "Mandatory"

    def test_c_returns_continuation(self):
        assert normalize_category("C") == "Continuation"

    def test_e_returns_earmark(self):
        assert normalize_category("E") == "Earmark"

    def test_o_returns_other(self):
        assert normalize_category("O") == "Other"

    def test_unknown_code_passthrough(self):
        assert normalize_category("unknown") == "unknown"

    def test_none_returns_none(self):
        assert normalize_category(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_category("") is None

    def test_whitespace_only_returns_none(self):
        assert normalize_category("   ") is None

    def test_strips_whitespace_before_lookup(self):
        assert normalize_category("  D  ") == "Discretionary"


# ─── normalize_funding_instrument ──────────────────────────────────────────────

class TestNormalizeFundingInstrument:
    def test_g_returns_grant(self):
        assert normalize_funding_instrument("G") == "Grant"

    def test_ca_returns_cooperative_agreement(self):
        assert normalize_funding_instrument("CA") == "Cooperative Agreement"

    def test_pc_returns_procurement_contract(self):
        assert normalize_funding_instrument("PC") == "Procurement Contract"

    def test_o_returns_other(self):
        assert normalize_funding_instrument("O") == "Other"

    def test_none_returns_none(self):
        assert normalize_funding_instrument(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_funding_instrument("") is None

    def test_whitespace_only_returns_none(self):
        assert normalize_funding_instrument("   ") is None

    def test_unknown_code_passthrough(self):
        assert normalize_funding_instrument("unknown") == "unknown"

    def test_strips_whitespace_before_lookup(self):
        assert normalize_funding_instrument("  CA  ") == "Cooperative Agreement"
