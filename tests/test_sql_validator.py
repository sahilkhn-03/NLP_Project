"""
tests/test_sql_validator.py
---------------------------
Unit tests for sql_validator.py.
Covers: SELECT-only enforcement, multi-statement rejection,
        forbidden keyword detection, injection patterns, and
        table name validation.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sql_validator import validate_sql, contains_injection_pattern, ValidationResult


# ---------------------------------------------------------------------------
# Valid SELECT queries
# ---------------------------------------------------------------------------

class TestValidSelects:
    def test_simple_select(self):
        r = validate_sql("SELECT * FROM students;")
        assert r.is_valid

    def test_select_with_where(self):
        r = validate_sql("SELECT name, marks FROM students WHERE marks > 80;")
        assert r.is_valid

    def test_select_with_join(self):
        r = validate_sql(
            "SELECT students.name, courses.course_name "
            "FROM students "
            "JOIN enrollments ON students.student_id = enrollments.student_id "
            "JOIN courses ON enrollments.course_id = courses.course_id;"
        )
        assert r.is_valid

    def test_select_aggregate(self):
        r = validate_sql("SELECT COUNT(*) AS total_count FROM students;")
        assert r.is_valid

    def test_clean_sql_ends_with_semicolon(self):
        r = validate_sql("SELECT * FROM students")
        assert r.is_valid
        assert r.clean_sql.endswith(";")

    def test_select_with_group_by(self):
        r = validate_sql(
            "SELECT department, COUNT(*) AS total_count "
            "FROM students GROUP BY department ORDER BY total_count DESC;"
        )
        assert r.is_valid


# ---------------------------------------------------------------------------
# Destructive / write operations – must all be rejected
# ---------------------------------------------------------------------------

class TestDestructiveOperations:
    DESTRUCTIVE = [
        "INSERT INTO students (name) VALUES ('hacker');",
        "UPDATE students SET marks = 100 WHERE 1=1;",
        "DELETE FROM students WHERE 1=1;",
        "DROP TABLE students;",
        "ALTER TABLE students ADD COLUMN x TEXT;",
        "CREATE TABLE evil (id INT);",
        "TRUNCATE TABLE students;",
        "REPLACE INTO students (name) VALUES ('x');",
        "ATTACH DATABASE '/tmp/evil.db' AS evil;",
        "DETACH DATABASE evil;",
        "EXEC xp_cmdshell('dir');",
        "GRANT ALL ON students TO public;",
        "REVOKE SELECT ON students FROM public;",
    ]

    @pytest.mark.parametrize("sql", DESTRUCTIVE)
    def test_destructive_sql_rejected(self, sql: str):
        r = validate_sql(sql)
        assert not r.is_valid, f"Should have rejected: {sql}"


# ---------------------------------------------------------------------------
# Multiple statements – must be rejected
# ---------------------------------------------------------------------------

class TestMultipleStatements:
    def test_two_selects(self):
        r = validate_sql("SELECT * FROM students; SELECT * FROM courses;")
        assert not r.is_valid

    def test_select_then_drop(self):
        r = validate_sql("SELECT * FROM students; DROP TABLE students;")
        # First caught by multi-stmt OR by forbidden keyword – either way invalid
        assert not r.is_valid

    def test_tailing_semicolon_ok(self):
        r = validate_sql("SELECT * FROM students;")
        assert r.is_valid  # Single trailing semicolon is fine


# ---------------------------------------------------------------------------
# Unknown table reference
# ---------------------------------------------------------------------------

class TestUnknownTables:
    def test_unknown_table(self):
        r = validate_sql("SELECT * FROM secrets;")
        assert not r.is_valid
        assert "secrets" in r.error.lower() or "unknown" in r.error.lower()

    def test_known_table_ok(self):
        r = validate_sql("SELECT * FROM courses;")
        assert r.is_valid


# ---------------------------------------------------------------------------
# SQL injection pattern detection (raw input guard)
# ---------------------------------------------------------------------------

class TestInjectionPatterns:
    INJECTIONS = [
        "'; DROP TABLE students; --",
        "1 OR '1'='1",
        "1 AND 1=1",
        "UNION SELECT * FROM students",
        "x'; EXEC xp_cmdshell('dir'); --",
        "SLEEP(5)",
        "BENCHMARK(1000000, MD5(1))",
        "WAITFOR DELAY '0:0:5'",
        "LOAD_FILE('/etc/passwd')",
        "x' INTO OUTFILE '/tmp/out.txt",
    ]

    @pytest.mark.parametrize("payload", INJECTIONS)
    def test_injection_detected(self, payload: str):
        assert contains_injection_pattern(payload), (
            f"Injection not detected in: {payload}"
        )

    def test_normal_question_not_flagged(self):
        assert not contains_injection_pattern("Show the top 5 students by marks")

    def test_another_normal_question(self):
        assert not contains_injection_pattern(
            "Find students whose attendance is below 75"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_sql(self):
        r = validate_sql("")
        assert not r.is_valid

    def test_whitespace_only(self):
        r = validate_sql("   ")
        assert not r.is_valid

    def test_case_insensitive_forbidden(self):
        r = validate_sql("insert into students values (1, 'x', 'AI', 99, 99);")
        assert not r.is_valid

    def test_mixed_case_drop(self):
        r = validate_sql("DrOp TaBle students;")
        assert not r.is_valid
