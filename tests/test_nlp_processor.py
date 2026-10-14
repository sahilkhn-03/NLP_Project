"""
tests/test_nlp_processor.py
---------------------------
Unit tests for the NLP parsing module.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from nlp_processor import parse_question, ParsedQuery


# ---------------------------------------------------------------------------
# Normalisation / basic parsing
# ---------------------------------------------------------------------------

class TestNormalisation:
    def test_empty_string(self):
        pq = parse_question("")
        assert pq.error is not None
        assert "empty" in pq.error.lower()

    def test_whitespace_only(self):
        pq = parse_question("   ")
        assert pq.error is not None

    def test_contraction_expansion(self):
        pq = parse_question("Who's the top student?")
        assert pq.error is None

    def test_returns_parsed_query_type(self):
        pq = parse_question("Show all students")
        assert isinstance(pq, ParsedQuery)


# ---------------------------------------------------------------------------
# Table detection
# ---------------------------------------------------------------------------

class TestTableDetection:
    def test_student_keyword(self):
        pq = parse_question("Show all students")
        assert "students" in pq.tables

    def test_course_keyword(self):
        pq = parse_question("List all courses")
        assert "courses" in pq.tables

    def test_enrollment_keyword(self):
        pq = parse_question("Show all enrollments")
        assert "enrollments" in pq.tables

    def test_default_table_is_students(self):
        pq = parse_question("Show the top 5 by marks")
        assert "students" in pq.tables


# ---------------------------------------------------------------------------
# Filter / WHERE detection
# ---------------------------------------------------------------------------

class TestFilterDetection:
    def test_greater_than(self):
        pq = parse_question("Find students who scored more than 80 marks")
        assert any(f.operator == ">" and f.value == 80.0 for f in pq.filters)

    def test_less_than(self):
        pq = parse_question("Students with marks less than 60")
        assert any(f.operator == "<" and f.value == 60.0 for f in pq.filters)

    def test_attendance_below(self):
        pq = parse_question("Find students whose attendance is below 75")
        assert any(f.column == "attendance" and f.operator == "<" for f in pq.filters)

    def test_attendance_above(self):
        pq = parse_question("Students with attendance above 90")
        assert any(f.column == "attendance" and f.operator == ">" for f in pq.filters)

    def test_department_ai(self):
        pq = parse_question("Show students from the AI department")
        dept_filters = [f for f in pq.filters if f.column == "department"]
        assert dept_filters, "Expected a department filter"
        assert dept_filters[0].value == "AI"

    def test_department_cs(self):
        pq = parse_question("Show students from the CS department")
        dept_filters = [f for f in pq.filters if f.column == "department"]
        assert dept_filters
        assert dept_filters[0].value == "CS"

    def test_grade_filter(self):
        pq = parse_question("Find students with grade A")
        grade_filters = [f for f in pq.filters if f.column == "grade"]
        assert grade_filters
        assert grade_filters[0].value == "A"


# ---------------------------------------------------------------------------
# Sort / ORDER BY detection
# ---------------------------------------------------------------------------

class TestSortDetection:
    def test_top_n_sets_desc(self):
        pq = parse_question("Show the top 5 students by marks")
        assert pq.order_dir == "DESC"

    def test_top_n_sets_limit(self):
        pq = parse_question("Show the top 5 students by marks")
        assert pq.limit == 5

    def test_bottom_sets_asc(self):
        pq = parse_question("Show the bottom 3 students by marks")
        assert pq.limit == 3

    def test_no_limit_by_default(self):
        pq = parse_question("Show all students")
        assert pq.limit is None


# ---------------------------------------------------------------------------
# Aggregate detection
# ---------------------------------------------------------------------------

class TestAggregateDetection:
    def test_count(self):
        pq = parse_question("Count the number of students")
        funcs = [f for f, _ in pq.aggregates]
        assert "COUNT" in funcs

    def test_average(self):
        pq = parse_question("Calculate the average marks")
        funcs = [f for f, _ in pq.aggregates]
        assert "AVG" in funcs

    def test_max(self):
        pq = parse_question("Find the highest marks")
        funcs = [f for f, _ in pq.aggregates]
        assert "MAX" in funcs

    def test_min(self):
        pq = parse_question("Find the lowest marks")
        funcs = [f for f, _ in pq.aggregates]
        assert "MIN" in funcs

    def test_group_by_department(self):
        pq = parse_question("Count students in each department")
        assert "department" in pq.group_by


# ---------------------------------------------------------------------------
# Join detection
# ---------------------------------------------------------------------------

class TestJoinDetection:
    def test_join_hint(self):
        pq = parse_question("List students with their enrolled course names")
        assert pq.needs_join is True

    def test_no_join_for_simple_query(self):
        pq = parse_question("Show all students")
        assert pq.needs_join is False
