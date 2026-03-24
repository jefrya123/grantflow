"""Shared normalization utilities for all ingest modules.

Pure Python — no database imports, no external dependencies beyond stdlib.
All functions are safe to call with None inputs.
"""

import json
import re
from datetime import datetime


# ─── Eligibility code mapping (Grants.gov applicant type codes) ────────────────

ELIGIBILITY_CODE_MAP: dict[str, str] = {
    "00": "State governments",
    "01": "County governments",
    "02": "City or township governments",
    "04": "Special district governments",
    "05": "Independent school districts",
    "06": "Public and State controlled institutions of higher education",
    "07": "Native American tribal governments (Federally recognized)",
    "08": "Public housing authorities/Indian housing authorities",
    "11": "Native American tribal organizations (other than Federally recognized)",
    "12": "Nonprofits (other than higher education) with 501(c)(3) status",
    "13": "Nonprofits without 501(c)(3) status",
    "20": "Private institutions of higher education",
    "21": "Individuals",
    "22": "For-profit organizations (other than small businesses)",
    "23": "Small businesses",
    "25": "Others (see agency eligibility text)",
    "99": "Unrestricted",
}


# ─── Agency name canonical mapping ────────────────────────────────────────────

AGENCY_NAME_MAP: dict[str, str] = {
    # Health and Human Services variants
    "HHS": "Department of Health and Human Services",
    "Dept. of Health and Human Services": "Department of Health and Human Services",
    "Dept of Health and Human Services": "Department of Health and Human Services",
    "DHHS": "Department of Health and Human Services",
    # Energy variants
    "DOE": "Department of Energy",
    "Dept. of Energy": "Department of Energy",
    "Dept of Energy": "Department of Energy",
    # Science foundations and institutes
    "NSF": "National Science Foundation",
    "NIH": "National Institutes of Health",
    "NASA": "National Aeronautics and Space Administration",
    # Agriculture
    "USDA": "Department of Agriculture",
    "Dept. of Agriculture": "Department of Agriculture",
    "Dept of Agriculture": "Department of Agriculture",
    # Defense
    "DOD": "Department of Defense",
    "Dept. of Defense": "Department of Defense",
    "Dept of Defense": "Department of Defense",
    # Education
    "ED": "Department of Education",
    "DOEd": "Department of Education",
    "Dept. of Education": "Department of Education",
    "Dept of Education": "Department of Education",
    # Transportation
    "DOT": "Department of Transportation",
    "Dept. of Transportation": "Department of Transportation",
    "Dept of Transportation": "Department of Transportation",
    # Commerce
    "DOC": "Department of Commerce",
    "Dept. of Commerce": "Department of Commerce",
    "Dept of Commerce": "Department of Commerce",
    # Labor
    "DOL": "Department of Labor",
    "Dept. of Labor": "Department of Labor",
    "Dept of Labor": "Department of Labor",
    # Interior
    "DOI": "Department of the Interior",
    "Dept. of the Interior": "Department of the Interior",
    "Dept of the Interior": "Department of the Interior",
    # Justice
    "DOJ": "Department of Justice",
    "Dept. of Justice": "Department of Justice",
    "Dept of Justice": "Department of Justice",
    # Veterans Affairs
    "VA": "Department of Veterans Affairs",
    "Dept. of Veterans Affairs": "Department of Veterans Affairs",
    "Dept of Veterans Affairs": "Department of Veterans Affairs",
    # EPA
    "EPA": "Environmental Protection Agency",
    # SBA
    "SBA": "Small Business Administration",
}

# ─── Date parsing formats (in priority order) ─────────────────────────────────

_DATE_FORMATS = (
    "%Y-%m-%d",   # ISO 8601 — most common, try first
    "%m/%d/%Y",   # MM/DD/YYYY (Grants.gov XML)
    "%Y%m%d",     # YYYYMMDD compact
    "%m%d%Y",     # MMDDYYYY compact (Grants.gov)
    "%b %d %Y",   # Jan 15 2024
    "%B %d %Y",   # January 15 2024
    "%Y-%m-%dT%H:%M:%S",  # ISO with time (SBIR)
    "%m/%d/%y",   # MM/DD/YY two-digit year
)


# ─── Public functions ──────────────────────────────────────────────────────────


def normalize_date(value: str | None) -> str | None:
    """Convert various date formats to ISO 8601 (YYYY-MM-DD).

    Returns None for None, empty input, or unparseable values.
    This is stricter than the old _normalize_date in grants_gov.py —
    unparseable values return None instead of the raw string.

    Pre-pass: datetime.fromisoformat() handles ISO 8601 with timezone offsets
    (e.g. "2024-03-15T00:00:00-04:00" or "2024-03-15T00:00:00Z") which
    strptime cannot parse.  Python 3.11+ supports the full ISO 8601 spec
    including Z suffix.  The _DATE_FORMATS loop handles non-ISO formats
    (MM/DD/YYYY, YYYYMMDD, etc.) that fromisoformat would reject.
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # Pre-pass: handle ISO 8601 with timezone offset
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def validate_award_amounts(
    floor: float | None,
    ceiling: float | None,
) -> tuple[float | None, float | None]:
    """Validate and sanitize award floor/ceiling values.

    Rules:
    - If either value is negative, return (None, None)
    - If floor > ceiling (and both provided), return (None, ceiling) — floor is invalid
    - If floor <= ceiling, return both as-is
    - Single-sided values (one None) are returned as-is provided the non-None value >= 0

    Returns (floor, ceiling) tuple.
    """
    # Check for negatives (exclude -0.0 which equals 0.0 in float comparison)
    if floor is not None and floor < 0:
        return (None, None)
    if ceiling is not None and ceiling < 0:
        return (None, None)

    # Both provided: validate ordering
    if floor is not None and ceiling is not None:
        if floor > ceiling:
            return (None, ceiling)

    return (floor, ceiling)


def normalize_eligibility_codes(codes: str | list | None) -> str:
    """Map raw eligibility codes to human-readable labels.

    Input can be:
    - None or empty → returns '[]'
    - A JSON string like '["12", "25"]'
    - A Python list like ["12", "25"]
    - A bare string code like "12"

    Unknown codes are kept as-is (not dropped).
    Returns a JSON string of translated labels.
    """
    if not codes and codes != 0:
        return "[]"

    # Parse input into a list of strings
    raw_codes: list[str]
    if isinstance(codes, list):
        raw_codes = [str(c).strip() for c in codes if c is not None]
    elif isinstance(codes, str):
        codes = codes.strip()
        if not codes:
            return "[]"
        # Try parsing as JSON array first
        if codes.startswith("["):
            try:
                parsed = json.loads(codes)
                raw_codes = [str(c).strip() for c in parsed if c is not None]
            except (json.JSONDecodeError, TypeError):
                raw_codes = [codes]
        else:
            # Bare string — treat as a single code
            raw_codes = [codes]
    else:
        return "[]"

    if not raw_codes:
        return "[]"

    # Map codes to labels; keep unknown codes as-is
    labels = [ELIGIBILITY_CODE_MAP.get(code, code) for code in raw_codes]
    return json.dumps(labels)


def normalize_agency_name(name: str | None) -> str | None:
    """Normalize agency name to canonical form.

    - Returns None for None or empty/whitespace-only input
    - Strips leading/trailing whitespace
    - Collapses multiple internal spaces to single space
    - Applies AGENCY_NAME_MAP for known abbreviations and variants
    """
    if not name:
        return None
    name = name.strip()
    if not name:
        return None

    # Collapse multiple internal spaces
    name = re.sub(r" {2,}", " ", name)

    # Apply canonical mapping
    return AGENCY_NAME_MAP.get(name, name)
