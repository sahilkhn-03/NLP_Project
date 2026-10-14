"""
nlp_processor.py
----------------
Converts a raw natural-language question into a structured
ParsedQuery object that sql_generator.py can turn into SQL.

Pipeline
--------
1. Normalise text (lower-case, strip punctuation, expand contractions)
2. Tokenise and remove stop-words
3. Detect tables mentioned (or infer a default)
4. Detect columns / aggregates / filters / sort / limit
5. Return a ParsedQuery dataclass
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema knowledge (mirrors database.py – imported lazily to avoid circular
# imports at test time)
# ---------------------------------------------------------------------------
TABLE_COLUMNS: dict[str, list[str]] = {
    "students":    ["student_id", "name", "department", "marks", "attendance"],
    "courses":     ["course_id", "course_name", "credits"],
    "enrollments": ["enrollment_id", "student_id", "course_id", "grade"],
}

# Words that map to a table
TABLE_KEYWORDS: dict[str, str] = {
    "student":     "students",
    "students":    "students",
    "student's":   "students",
    "course":      "courses",
    "courses":     "courses",
    "subject":     "courses",
    "subjects":    "courses",
    "enrollment":  "enrollments",
    "enrollments": "enrollments",
    "enrolled":    "enrollments",
    "enrol":       "enrollments",
}

# Words that map to a column
COLUMN_KEYWORDS: dict[str, tuple[str, str]] = {
    # keyword -> (table, column)
    "marks":        ("students", "marks"),
    "mark":         ("students", "marks"),
    "score":        ("students", "marks"),
    "scores":       ("students", "marks"),
    "attendance":   ("students", "attendance"),
    "present":      ("students", "attendance"),
    "name":         ("students", "name"),
    "names":        ("students", "name"),
    "department":   ("students", "department"),
    "dept":         ("students", "department"),
    "departments":  ("students", "department"),
    "credit":       ("courses",  "credits"),
    "credits":      ("courses",  "credits"),
    "course_name":  ("courses",  "course_name"),
    "course":       ("courses",  "course_name"),
    "subject":      ("courses",  "course_name"),
    "grade":        ("enrollments", "grade"),
    "grades":       ("enrollments", "grade"),
    "gpa":          ("enrollments", "grade"),
}

# Aggregate intent patterns
AGG_PATTERNS: list[tuple[re.Pattern, str, str | None]] = [
    # (pattern, agg_function, column_hint)
    # NOTE: 'top' / 'bottom' are intentionally excluded – they mean SORT+LIMIT
    (re.compile(r"\b(count|how many|number of|total number)\b"), "COUNT", None),
    (re.compile(r"\b(average|avg|mean)\b"),                       "AVG",   "marks"),
    (re.compile(r"\b(sum|total)\b"),                              "SUM",   "marks"),
    (re.compile(r"\b(max|maximum|highest|most)\b"),               "MAX",   "marks"),
    (re.compile(r"\b(min|minimum|lowest|least)\b"),               "MIN",   "marks"),
]

# Comparison / filter patterns
FILTER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(more than|greater than|above|over|>)\s+(\d+(?:\.\d+)?)"),  ">"),
    (re.compile(r"(less than|lower than|below|under|<)\s+(\d+(?:\.\d+)?)"),   "<"),
    (re.compile(r"(at least|minimum of|>=)\s+(\d+(?:\.\d+)?)"),               ">="),
    (re.compile(r"(at most|maximum of|<=)\s+(\d+(?:\.\d+)?)"),                "<="),
    (re.compile(r"(equal to|equals|=|is)\s+(\d+(?:\.\d+)?)"),                 "="),
    (re.compile(r"(not equal|!=|<>)\s+(\d+(?:\.\d+)?)"),                      "!="),
]

# Department / string value extraction
DEPT_PATTERN = re.compile(
    r"\b(?:from|in|of|department|dept)\s+([A-Za-z]{2,20})\b"
)
NAMED_DEPT = re.compile(r"\b(AI|CS|DS|Data Science|Computer Science|Artificial Intelligence)\b", re.IGNORECASE)

# Limit patterns
LIMIT_PATTERNS = [
    re.compile(r"\btop\s+(\d+)\b"),
    re.compile(r"\bbottom\s+(\d+)\b"),
    re.compile(r"\bfirst\s+(\d+)\b"),
    re.compile(r"\blast\s+(\d+)\b"),
    re.compile(r"\blimit\s+(\d+)\b"),
]

# Sort direction
ASC_KW  = re.compile(r"\b(ascending|asc|lowest first|minimum first|alphabetically)\b")
DESC_KW = re.compile(r"\b(descending|desc|highest first|maximum first|top)\b")

# Group-by hint
GROUP_KW = re.compile(r"\b(group by|each|per|by department|by dept|for each)\b")

# Join hint words
JOIN_KW = re.compile(r"\b(with their|along with|join|joined|including course|course names?)\b")

# Named-value string filter (e.g. "grade A", "grade B")
GRADE_PATTERN = re.compile(r"\bgrade\s+([A-Fa-f])\b")

STOP_WORDS = {
    "the", "a", "an", "is", "are", "of", "and", "or", "in", "for",
    "to", "with", "that", "which", "who", "all", "show", "list",
    "find", "get", "give", "display", "print", "what", "where",
    "how", "tell", "me", "please", "can", "you", "i", "want",
    "need", "have", "has", "do", "does", "did", "their", "its",
    "having", "been", "this", "those", "these", "let", "from",
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class Filter:
    column:   str
    operator: str          # >, <, >=, <=, =, !=, LIKE, IN
    value:    str | float  # raw value; parameterised later


@dataclass
class ParsedQuery:
    tables:     list[str]            = field(default_factory=list)
    columns:    list[str]            = field(default_factory=list)
    filters:    list[Filter]         = field(default_factory=list)
    aggregates: list[tuple[str, str]]= field(default_factory=list)  # [(func, col)]
    group_by:   list[str]            = field(default_factory=list)
    order_by:   str | None           = None
    order_dir:  str                  = "ASC"
    limit:      int | None           = None
    needs_join: bool                 = False
    intent:     str                  = "SELECT"   # SELECT | AGGREGATE | COUNT
    raw_text:   str                  = ""
    error:      str | None           = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_question(question: str) -> ParsedQuery:
    """
    Main entry point.  Accepts a raw English question and returns a
    ParsedQuery describing what SQL to build.
    """
    pq = ParsedQuery(raw_text=question)

    if not question or not question.strip():
        pq.error = "Empty question. Please type a question."
        return pq

    text = _normalise(question)
    logger.debug("Normalised: %s", text)

    _detect_tables(text, pq)
    _detect_limit(text, pq)
    _detect_sort(text, pq)
    _detect_aggregates(text, pq)
    _detect_filters(text, pq)
    _detect_group_by(text, pq)
    _detect_join(text, pq)
    _detect_columns(text, pq)
    _resolve_intent(pq)
    _apply_defaults(pq)

    return pq


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lower-case, expand common contractions, strip special chars."""
    text = text.lower().strip()
    contractions = {
        "who's": "who is", "what's": "what is", "don't": "do not",
        "doesn't": "does not", "didn't": "did not", "isn't": "is not",
        "aren't": "are not", "can't": "cannot", "won't": "will not",
        "student's": "student", "students'": "students",
    }
    for k, v in contractions.items():
        text = text.replace(k, v)
    # keep letters, digits, spaces, %, >, <, =, ., !
    text = re.sub(r"[^a-z0-9\s%><!=.,']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detect_tables(text: str, pq: ParsedQuery) -> None:
    found: list[str] = []
    for kw, tbl in TABLE_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", text) and tbl not in found:
            found.append(tbl)
    pq.tables = found if found else ["students"]   # safe default


def _detect_limit(text: str, pq: ParsedQuery) -> None:
    for pat in LIMIT_PATTERNS:
        m = pat.search(text)
        if m:
            pq.limit = int(m.group(1))
            return


def _detect_sort(text: str, pq: ParsedQuery) -> None:
    if DESC_KW.search(text):
        pq.order_dir = "DESC"
    elif ASC_KW.search(text):
        pq.order_dir = "ASC"

    # Infer sort column from context – but only when a LIMIT is also requested
    # (i.e. "top 5" means sort+limit, not aggregate)
    has_limit = any(p.search(text) for p in LIMIT_PATTERNS)
    if re.search(r"\b(top|highest|maximum|most|best)\b", text):
        pq.order_by   = "marks"
        pq.order_dir  = "DESC"
        if "students" not in pq.tables:
            pq.tables.append("students")
    elif re.search(r"\b(lowest|minimum|least|worst|bottom)\b", text) and has_limit:
        pq.order_by   = "marks"
        pq.order_dir  = "ASC"
    elif re.search(r"\b(alphabetical|by name)\b", text):
        pq.order_by  = "name"
        pq.order_dir = "ASC"


def _detect_aggregates(text: str, pq: ParsedQuery) -> None:
    for pat, func, col_hint in AGG_PATTERNS:
        if pat.search(text):
            # Try to find the target column in the text
            col = _find_agg_column(text, col_hint)
            pq.aggregates.append((func, col))


def _find_agg_column(text: str, hint: str | None) -> str:
    for kw, (_, col) in COLUMN_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", text):
            return col
    return hint or "*"


def _detect_filters(text: str, pq: ParsedQuery) -> None:
    # Track which columns already have a filter to avoid duplicates
    filtered_cols: set[str] = set()

    # Handle attendance specifically FIRST (before generic numeric pattern)
    att_below = re.search(r"attendance\s+(?:is\s+)?(?:below|less than|under)\s+(\d+)", text)
    if att_below:
        pq.filters.append(Filter(column="attendance", operator="<", value=float(att_below.group(1))))
        filtered_cols.add("attendance")

    att_above = re.search(r"attendance\s+(?:is\s+)?(?:above|more than|over|greater than)\s+(\d+)", text)
    if att_above:
        pq.filters.append(Filter(column="attendance", operator=">", value=float(att_above.group(1))))
        filtered_cols.add("attendance")

    # Generic numeric comparisons (skip columns already handled above)
    for pat, op in FILTER_PATTERNS:
        m = pat.search(text)
        if m:
            val = float(m.group(2))
            col = _nearest_column(text, m.start())
            if col not in filtered_cols:
                pq.filters.append(Filter(column=col, operator=op, value=val))
                filtered_cols.add(col)

    # Department / string equality
    # Explicit dept names first
    m = NAMED_DEPT.search(text)
    if m:
        raw = m.group(1)
        dept_map = {
            "data science":           "DS",
            "computer science":       "CS",
            "artificial intelligence":"AI",
        }
        dept = dept_map.get(raw.lower(), raw.upper())
        pq.filters.append(Filter(column="department", operator="=", value=dept))
    else:
        # Pattern like "from AI" or "in CS"
        m2 = DEPT_PATTERN.search(text)
        if m2:
            candidate = m2.group(1).upper()
            if candidate in ("AI", "CS", "DS"):
                pq.filters.append(Filter(column="department", operator="=", value=candidate))

    # Grade filter
    m3 = GRADE_PATTERN.search(text)
    if m3:
        pq.filters.append(Filter(column="grade", operator="=", value=m3.group(1).upper()))
        if "enrollments" not in pq.tables:
            pq.tables.append("enrollments")


def _nearest_column(text: str, pos: int) -> str:
    """Guess which column a comparison refers to based on surrounding words."""
    snippet = text[max(0, pos - 60): pos + 20]
    for kw, (_, col) in COLUMN_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", snippet):
            return col
    return "marks"   # safe default


def _detect_group_by(text: str, pq: ParsedQuery) -> None:
    if GROUP_KW.search(text):
        if re.search(r"\b(department|dept)\b", text):
            pq.group_by = ["department"]
        elif re.search(r"\b(course|subject)\b", text):
            pq.group_by = ["course_name"]


def _detect_join(text: str, pq: ParsedQuery) -> None:
    if JOIN_KW.search(text):
        pq.needs_join = True
        for tbl in ("students", "courses", "enrollments"):
            if tbl not in pq.tables:
                pq.tables.append(tbl)


def _detect_columns(text: str, pq: ParsedQuery) -> None:
    """Explicit column hints (when user asks 'show name and marks' etc.)."""
    cols: list[str] = []
    for kw, (_, col) in COLUMN_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", text) and col not in cols:
            cols.append(col)
    pq.columns = cols


def _resolve_intent(pq: ParsedQuery) -> None:
    if pq.aggregates:
        funcs = [f for f, _ in pq.aggregates]
        pq.intent = "COUNT" if funcs == ["COUNT"] else "AGGREGATE"
    else:
        pq.intent = "SELECT"


def _apply_defaults(pq: ParsedQuery) -> None:
    """Ensure we always have at least one table and sensible sort."""
    if not pq.tables:
        pq.tables = ["students"]

    # If order_by column mentioned but no explicit direction, use DESC for marks
    if pq.order_by == "marks" and pq.order_dir not in ("ASC", "DESC"):
        pq.order_dir = "DESC"
