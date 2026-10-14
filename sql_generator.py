"""
sql_generator.py
----------------
Converts a ParsedQuery (from nlp_processor.py) into a SQL string and
a plain-English explanation.  No query is executed here; execution is
handled by database.py after validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from nlp_processor import ParsedQuery, Filter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema knowledge (same as database.py to avoid circular import)
# ---------------------------------------------------------------------------
TABLE_COLUMNS: dict[str, list[str]] = {
    "students":    ["student_id", "name", "department", "marks", "attendance"],
    "courses":     ["course_id", "course_name", "credits"],
    "enrollments": ["enrollment_id", "student_id", "course_id", "grade"],
}

# Join conditions between table pairs
JOIN_CONDITIONS: dict[frozenset, tuple[str, str, str]] = {
    frozenset({"students", "enrollments"}): (
        "students", "enrollments",
        "students.student_id = enrollments.student_id",
    ),
    frozenset({"courses", "enrollments"}): (
        "courses", "enrollments",
        "courses.course_id = enrollments.course_id",
    ),
    frozenset({"students", "courses"}): (
        None, None,   # needs enrollments as bridge
        None,
    ),
}


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class GeneratedQuery:
    sql:         str
    params:      tuple
    explanation: str
    error:       str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_sql(pq: ParsedQuery) -> GeneratedQuery:
    """
    Convert a ParsedQuery to a SQL string + plain-English explanation.
    Returns GeneratedQuery; .error is non-None on failure.
    """
    if pq.error:
        return GeneratedQuery(sql="", params=(), explanation="", error=pq.error)

    try:
        if pq.intent in ("COUNT", "AGGREGATE"):
            return _build_aggregate(pq)
        else:
            return _build_select(pq)
    except Exception as exc:
        logger.exception("SQL generation error")
        return GeneratedQuery(
            sql="", params=(), explanation="",
            error=f"Could not generate SQL: {exc}",
        )


# ---------------------------------------------------------------------------
# SELECT builder
# ---------------------------------------------------------------------------

def _build_select(pq: ParsedQuery) -> GeneratedQuery:
    # -- SELECT clause --
    primary_table = pq.tables[0]
    select_cols   = _resolve_select_cols(pq, primary_table)

    # -- FROM / JOIN clause --
    from_clause, join_clause = _build_from_join(pq)

    # -- WHERE clause --
    where_clause, params = _build_where(pq)

    # -- ORDER BY --
    order_clause = _build_order(pq)

    # -- LIMIT --
    limit_clause = f"LIMIT {pq.limit}" if pq.limit else ""

    # Assemble
    parts = [
        f"SELECT {select_cols}",
        f"FROM {from_clause}",
    ]
    if join_clause:
        parts.append(join_clause)
    if where_clause:
        parts.append(f"WHERE {where_clause}")
    if order_clause:
        parts.append(f"ORDER BY {order_clause}")
    if limit_clause:
        parts.append(limit_clause)

    sql = "\n".join(parts) + ";"
    explanation = _explain_select(pq, select_cols, where_clause, order_clause, limit_clause)
    return GeneratedQuery(sql=sql, params=params, explanation=explanation)


# ---------------------------------------------------------------------------
# AGGREGATE builder
# ---------------------------------------------------------------------------

def _build_aggregate(pq: ParsedQuery) -> GeneratedQuery:
    primary_table = pq.tables[0]

    # Build SELECT expressions
    agg_exprs: list[str] = []
    for func, col in pq.aggregates:
        if func == "COUNT":
            agg_exprs.append("COUNT(*) AS total_count")
        else:
            # validate column
            qualified_col = _qualify(col, pq.tables)
            agg_exprs.append(f"{func}({qualified_col}) AS {func.lower()}_{col}")

    # Add group-by columns to SELECT
    for gcol in pq.group_by:
        qualified_gcol = _qualify(gcol, pq.tables)
        if qualified_gcol not in agg_exprs:
            agg_exprs.insert(0, qualified_gcol)

    select_cols = ", ".join(agg_exprs) if agg_exprs else "COUNT(*) AS total_count"

    # FROM / JOIN
    from_clause, join_clause = _build_from_join(pq)

    # WHERE
    where_clause, params = _build_where(pq)

    # GROUP BY
    group_clause = ""
    if pq.group_by:
        qualified_groups = [_qualify(g, pq.tables) for g in pq.group_by]
        group_clause = "GROUP BY " + ", ".join(qualified_groups)

    # ORDER BY (for aggregates: order by agg result if no group-by)
    order_clause = ""
    if pq.group_by and pq.aggregates:
        # Order by aggregate descending by default
        _, col = pq.aggregates[0]
        func, _ = pq.aggregates[0]
        if func == "COUNT":
            order_clause = "ORDER BY total_count DESC"
        else:
            order_clause = f"ORDER BY {func.lower()}_{col} DESC"
    elif pq.order_by:
        raw_order = _build_order(pq)
        order_clause = f"ORDER BY {raw_order}" if raw_order else ""

    limit_clause = f"LIMIT {pq.limit}" if pq.limit else ""

    parts = [f"SELECT {select_cols}", f"FROM {from_clause}"]
    if join_clause:
        parts.append(join_clause)
    if where_clause:
        parts.append(f"WHERE {where_clause}")
    if group_clause:
        parts.append(group_clause)
    if order_clause:
        parts.append(order_clause)
    if limit_clause:
        parts.append(limit_clause)

    sql = "\n".join(parts) + ";"
    explanation = _explain_aggregate(pq, select_cols, where_clause, group_clause)
    return GeneratedQuery(sql=sql, params=params, explanation=explanation)


# ---------------------------------------------------------------------------
# Clause builders
# ---------------------------------------------------------------------------

def _resolve_select_cols(pq: ParsedQuery, primary_table: str) -> str:
    """Choose which columns to SELECT."""
    if pq.needs_join:
        # For joins return useful readable columns
        return "students.name, students.department, students.marks, courses.course_name, enrollments.grade"

    # For ranking queries (sort + limit) always return the full row so the
    # result table is readable (not just the sort column)
    if pq.order_by and pq.limit and not pq.aggregates:
        return f"{primary_table}.*"

    if not pq.columns:
        # No specific columns requested → return all of primary table
        return f"{primary_table}.*"

    resolved: list[str] = []
    for col in pq.columns:
        resolved.append(_qualify(col, pq.tables))
    return ", ".join(resolved) if resolved else f"{primary_table}.*"


def _qualify(col: str, tables: list[str]) -> str:
    """Prefix column with its table name for unambiguous references."""
    for tbl in tables:
        if col in TABLE_COLUMNS.get(tbl, []):
            return f"{tbl}.{col}"
    return col


def _build_from_join(pq: ParsedQuery) -> tuple[str, str]:
    """Return (from_clause, optional JOIN lines)."""
    tables = pq.tables

    if len(tables) == 1:
        return tables[0], ""

    if len(tables) == 2:
        key = frozenset(tables)
        if key in JOIN_CONDITIONS:
            t1, t2, cond = JOIN_CONDITIONS[key]
            if cond:
                return t1, f"JOIN {t2} ON {cond}"

    # Three tables: students ↔ enrollments ↔ courses (via bridge)
    if set(tables) >= {"students", "courses"}:
        return (
            "students",
            "JOIN enrollments ON students.student_id = enrollments.student_id\n"
            "JOIN courses ON enrollments.course_id = courses.course_id",
        )

    # Fallback: natural join of remaining tables
    primary = tables[0]
    joins: list[str] = []
    for tbl in tables[1:]:
        key = frozenset({primary, tbl})
        if key in JOIN_CONDITIONS:
            _, t2, cond = JOIN_CONDITIONS[key]
            if cond:
                joins.append(f"JOIN {t2} ON {cond}")
    return primary, "\n".join(joins)


def _build_where(pq: ParsedQuery) -> tuple[str, tuple]:
    """Build parameterised WHERE clause."""
    if not pq.filters:
        return "", ()

    clauses: list[str] = []
    params:  list      = []

    for f in pq.filters:
        qualified_col = _qualify(f.column, pq.tables)
        if f.operator == "LIKE":
            clauses.append(f"{qualified_col} LIKE ?")
            params.append(f"%{f.value}%")
        else:
            clauses.append(f"{qualified_col} {f.operator} ?")
            params.append(f.value)

    return " AND ".join(clauses), tuple(params)


def _build_order(pq: ParsedQuery) -> str:
    if not pq.order_by:
        return ""
    qualified = _qualify(pq.order_by, pq.tables)
    return f"{qualified} {pq.order_dir}"


# ---------------------------------------------------------------------------
# Explanation builders
# ---------------------------------------------------------------------------

def _explain_select(pq, select_cols, where_clause, order_clause, limit_clause) -> str:
    lines: list[str] = []

    if pq.needs_join:
        lines.append(
            "This query **joins** the `students`, `enrollments`, and `courses` tables "
            "so each row shows a student alongside the course they are enrolled in."
        )
    else:
        primary = pq.tables[0]
        lines.append(f"This query **retrieves records** from the **`{primary}`** table.")

    if where_clause:
        lines.append(f"It **filters** rows where: `{where_clause.replace('?', '<value>')}`.")

    if order_clause:
        direction = "highest first" if "DESC" in order_clause else "lowest first"
        lines.append(f"Results are **sorted** by `{order_clause}` ({direction}).")

    if limit_clause:
        lines.append(f"Only the **top {pq.limit}** rows are returned.")

    return "  \n".join(lines)


def _explain_aggregate(pq, select_cols, where_clause, group_clause) -> str:
    lines: list[str] = []

    funcs = [f for f, _ in pq.aggregates]
    if "COUNT" in funcs:
        lines.append("This query **counts** the number of matching records.")
    if "AVG" in funcs:
        lines.append("This query **calculates the average** of the specified column.")
    if "MAX" in funcs:
        lines.append("This query finds the **maximum value** in the specified column.")
    if "MIN" in funcs:
        lines.append("This query finds the **minimum value** in the specified column.")
    if "SUM" in funcs:
        lines.append("This query **sums** the values in the specified column.")

    if where_clause:
        lines.append(f"It **filters** rows where: `{where_clause.replace('?', '<value>')}`.")

    if group_clause:
        lines.append(f"Results are **grouped** so you see one row per group.")

    return "  \n".join(lines) if lines else "Aggregate query generated."
