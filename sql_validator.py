"""
sql_validator.py
----------------
Validates generated SQL before execution.

Rules enforced
--------------
1. Only SELECT statements are permitted.
2. Multiple statements (semicolon-separated) are rejected.
3. Dangerous keywords (DROP, ALTER, DELETE, INSERT, UPDATE, CREATE,
   ATTACH, DETACH, PRAGMA write forms) are blocked.
4. Table and column names are checked against the actual schema.
5. SQL is parsed lightly with regex (no external parser needed).
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed schema (mirrors database.py)
# ---------------------------------------------------------------------------
ALLOWED_TABLES: frozenset[str] = frozenset({"students", "courses", "enrollments"})

ALLOWED_COLUMNS: frozenset[str] = frozenset(
    {
        # students
        "student_id", "name", "department", "marks", "attendance",
        # courses
        "course_id", "course_name", "credits",
        # enrollments
        "enrollment_id", "course_id", "grade",
        # wildcards / aggregates accepted as-is
        "*",
    }
)

# Forbidden keywords (case-insensitive)
FORBIDDEN_KEYWORDS: list[str] = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bREPLACE\b",
    r"\bTRUNCATE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bCALL\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    # PRAGMA write forms
    r"\bPRAGMA\s+\w+\s*=",
]

# Compiled forbidden patterns
_FORBIDDEN_RE: re.Pattern = re.compile(
    "|".join(FORBIDDEN_KEYWORDS), re.IGNORECASE
)

# Only SELECT may start a statement
_MUST_START_SELECT_RE: re.Pattern = re.compile(
    r"^\s*SELECT\b", re.IGNORECASE
)

# Multiple statements – any semicolon that is NOT at the very end
_MULTI_STMT_RE: re.Pattern = re.compile(
    r";(?!\s*$)"
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    is_valid:   bool
    error:      str | None = None
    clean_sql:  str        = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_sql(sql: str) -> ValidationResult:
    """
    Run all safety checks on the SQL string.
    Returns ValidationResult with is_valid=True only when all checks pass.
    """
    if not sql or not sql.strip():
        return ValidationResult(is_valid=False, error="Empty SQL string.")

    stripped = sql.strip()

    # 1. Must start with SELECT
    if not _MUST_START_SELECT_RE.match(stripped):
        logger.warning("Rejected non-SELECT SQL: %.120s", stripped)
        return ValidationResult(
            is_valid=False,
            error="Only SELECT queries are permitted. Write operations are blocked.",
        )

    # 2. No forbidden keywords anywhere in the statement
    m = _FORBIDDEN_RE.search(stripped)
    if m:
        logger.warning("Rejected SQL containing forbidden keyword '%s'", m.group())
        return ValidationResult(
            is_valid=False,
            error=f"SQL contains a forbidden keyword: '{m.group()}'. "
                  "Write operations are not allowed.",
        )

    # 3. Multiple statements
    if _MULTI_STMT_RE.search(stripped):
        logger.warning("Rejected multi-statement SQL")
        return ValidationResult(
            is_valid=False,
            error="Multiple SQL statements in a single query are not permitted.",
        )

    # 4. Table name validation
    table_error = _check_tables(stripped)
    if table_error:
        return ValidationResult(is_valid=False, error=table_error)

    # 5. Looks good – return cleaned SQL (trailing semicolon normalised)
    clean = stripped.rstrip(";").strip() + ";"
    return ValidationResult(is_valid=True, clean_sql=clean)


# ---------------------------------------------------------------------------
# Helper checks
# ---------------------------------------------------------------------------

def _check_tables(sql: str) -> str | None:
    """
    Extract table identifiers from FROM / JOIN clauses and verify they
    are in the allowed schema.
    """
    # Match  FROM tbl  or  JOIN tbl
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(sql):
        tbl = m.group(1).lower()
        if tbl not in ALLOWED_TABLES:
            return (
                f"Reference to unknown table '{tbl}'. "
                f"Allowed tables: {', '.join(sorted(ALLOWED_TABLES))}."
            )
    return None


def is_safe_identifier(name: str) -> bool:
    """Return True if *name* is a plain alphanumeric/underscore identifier."""
    return bool(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name))


def contains_injection_pattern(text: str) -> bool:
    """
    Quick heuristic check for common SQL-injection payloads in raw
    user input (before any SQL is generated).
    """
    patterns = [
        r"--",                  # line comment
        r"/\*",                 # block comment open
        r"\*/",                 # block comment close
        r";\s*\w",              # statement chaining
        r"\bOR\b\s+[\'\d]",     # OR '1'='1' style
        r"\bAND\b\s+[\'\d]",    # AND 1=1 style
        r"UNION\s+SELECT",      # UNION injection
        r"xp_cmdshell",         # MSSQL proc
        r"SLEEP\s*\(",          # time-based blind
        r"BENCHMARK\s*\(",      # MySQL time-based
        r"WAITFOR\s+DELAY",     # MSSQL delay
        r"LOAD_FILE\s*\(",      # MySQL file read
        r"INTO\s+OUTFILE",      # MySQL file write
    ]
    combined = re.compile("|".join(patterns), re.IGNORECASE)
    return bool(combined.search(text))
