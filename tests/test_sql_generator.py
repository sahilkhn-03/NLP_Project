"""
tests/test_sql_generator.py
---------------------------
Unit tests for sql_generator.py.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from nlp_processor import parse_question
from sql_generator import generate_sql, GeneratedQuery


def gen(question: str) -> GeneratedQuery:
    return generate_sql(parse_question(question))


# ---------------------------------------------------------------------------
# Basic SELECT
# ---------------------------------------------------------------------------

class TestBasicSelect:
    def test_show_all_students(self):
        g = gen("Show all students")
        assert g.error is None
        assert "SELECT" in g.sql.upper()
        assert "students" in g.sql.lower()

    def test_list_all_courses(self):
        g = gen("List all courses")
        assert g.error is None
        assert "courses" in g.sql.lower()

    def test_no_error_on_simple_question(self):
        g = gen("Show all students")
        assert g.error is None
        assert g.sql.strip().endswith(";")


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_marks_greater_than(self):
        g = gen("Find students who scored more than 80 marks")
        assert g.error is None
        sql_up = g.sql.upper()
        assert "WHERE" in sql_up
        assert ">" in g.sql
        assert 80.0 in g.params

    def test_attendance_below(self):
        g = gen("Find students whose attendance is below 75")
        assert g.error is None
        assert "WHERE" in g.sql.upper()
        assert 75.0 in g.params

    def test_department_filter(self):
        g = gen("Show students from the AI department")
        assert g.error is None
        assert "WHERE" in g.sql.upper()
        assert "AI" in g.params

    def test_credits_greater_than(self):
        g = gen("Show courses with more than 3 credits")
        assert g.error is None
        assert "courses" in g.sql.lower()
        assert "WHERE" in g.sql.upper()


# ---------------------------------------------------------------------------
# Sorting & Limiting
# ---------------------------------------------------------------------------

class TestSortingLimiting:
    def test_top_5_has_limit(self):
        g = gen("Show the top 5 students by marks")
        assert g.error is None
        assert "LIMIT 5" in g.sql.upper()

    def test_top_5_has_order_desc(self):
        g = gen("Show the top 5 students by marks")
        assert "DESC" in g.sql.upper()

    def test_top_3(self):
        g = gen("Show top 3 students by marks")
        assert "LIMIT 3" in g.sql.upper()


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

class TestAggregates:
    def test_count_students(self):
        g = gen("Count the number of students")
        assert g.error is None
        assert "COUNT" in g.sql.upper()

    def test_average_marks(self):
        g = gen("Calculate the average marks of students")
        assert g.error is None
        assert "AVG" in g.sql.upper()

    def test_max_marks(self):
        g = gen("Find the highest marks")
        assert g.error is None
        assert "MAX" in g.sql.upper()

    def test_min_marks(self):
        g = gen("Find the lowest marks")
        assert g.error is None
        assert "MIN" in g.sql.upper()

    def test_count_per_department(self):
        g = gen("Count the number of students in each department")
        assert g.error is None
        assert "GROUP BY" in g.sql.upper()
        assert "COUNT" in g.sql.upper()


# ---------------------------------------------------------------------------
# Joins
# ---------------------------------------------------------------------------

class TestJoins:
    def test_join_present(self):
        g = gen("List students with their enrolled course names")
        assert g.error is None
        assert "JOIN" in g.sql.upper()

    def test_join_references_multiple_tables(self):
        g = gen("List students with their enrolled course names")
        sql_lower = g.sql.lower()
        assert "students" in sql_lower
        assert "courses" in sql_lower


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------

class TestExplanation:
    def test_explanation_nonempty(self):
        g = gen("Show all students")
        assert g.explanation and len(g.explanation) > 5

    def test_aggregate_explanation(self):
        g = gen("Count students in each department")
        assert g.explanation


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_question(self):
        g = gen("")
        assert g.error is not None

    def test_nonsense_question_produces_some_output_or_error(self):
        # Should not raise an exception
        g = gen("xyzzy blorp foobar")
        # Either an error or a fallback SELECT is fine
        assert g is not None
