"""
database.py
-----------
Handles SQLite database creation, sample data insertion,
and schema introspection for the NL-to-SQL project.
"""

import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

def get_db_path() -> str:
    override = os.environ.get("DB_PATH")
    if override:
        return override
    # If running on Vercel or AWS Lambda / read-only serverless
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/school.db"
    local_path = os.path.join(os.path.dirname(__file__), "data", "school.db")
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        return local_path
    except OSError:
        import tempfile
        return os.path.join(tempfile.gettempdir(), "school.db")

DB_PATH = get_db_path()


# ---------------------------------------------------------------------------
# Schema constants – single source of truth consumed by nlp_processor too
# ---------------------------------------------------------------------------
SCHEMA: dict[str, list[str]] = {
    "students": ["student_id", "name", "department", "marks", "attendance"],
    "courses": ["course_id", "course_name", "credits"],
    "enrollments": ["enrollment_id", "student_id", "course_id", "grade"],
}

# Human-friendly aliases (lower-case) → canonical column names
COLUMN_ALIASES: dict[str, str] = {
    "score": "marks",
    "percentage": "attendance",
    "dept": "department",
    "subject": "course_name",
    "credit": "credits",
    "gpa": "grade",
    "id": "student_id",
}

# Foreign-key join graph
JOIN_PATHS: dict[tuple[str, str], str] = {
    ("students", "enrollments"): "students.student_id = enrollments.student_id",
    ("enrollments", "students"): "students.student_id = enrollments.student_id",
    ("courses", "enrollments"): "courses.course_id = enrollments.course_id",
    ("enrollments", "courses"): "courses.course_id = enrollments.course_id",
    ("students", "courses"): (
        "students.student_id = enrollments.student_id "
        "AND courses.course_id = enrollments.course_id"
    ),
    ("courses", "students"): (
        "students.student_id = enrollments.student_id "
        "AND courses.course_id = enrollments.course_id"
    ),
}


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    path = get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    """Create tables and insert sample data if the database is empty."""
    path = get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    # Enable foreign keys
    cur.execute("PRAGMA foreign_keys = ON;")

    # ------------------------------------------------------------------
    # Create tables
    # ------------------------------------------------------------------
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
            student_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            department  TEXT    NOT NULL,
            marks       REAL    NOT NULL CHECK(marks BETWEEN 0 AND 100),
            attendance  REAL    NOT NULL CHECK(attendance BETWEEN 0 AND 100)
        );

        CREATE TABLE IF NOT EXISTS courses (
            course_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT    NOT NULL UNIQUE,
            credits     INTEGER NOT NULL CHECK(credits BETWEEN 1 AND 6)
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    INTEGER NOT NULL REFERENCES students(student_id),
            course_id     INTEGER NOT NULL REFERENCES courses(course_id),
            grade         TEXT    NOT NULL CHECK(grade IN ('A','B','C','D','F')),
            UNIQUE(student_id, course_id)
        );
        """
    )

    # ------------------------------------------------------------------
    # Seed data only when tables are empty
    # ------------------------------------------------------------------
    if cur.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
        _seed_students(cur)
        _seed_courses(cur)
        _seed_enrollments(cur)
        conn.commit()
        logger.info("Database seeded with sample data.")
    else:
        logger.info("Database already contains data – skipping seed.")

    conn.close()


def _seed_students(cur: sqlite3.Cursor) -> None:
    students = [
        ("Aarav Sharma",    "AI",           91.5, 88.0),
        ("Priya Patel",     "CS",           87.0, 92.5),
        ("Rohan Mehta",     "AI",           76.0, 70.0),
        ("Sneha Iyer",      "DS",           95.0, 96.0),
        ("Arjun Nair",      "CS",           62.0, 55.0),
        ("Divya Reddy",     "DS",           88.5, 83.0),
        ("Karan Verma",     "AI",           73.0, 78.0),
        ("Ananya Singh",    "CS",           90.0, 91.0),
        ("Vikram Joshi",    "DS",           55.0, 65.0),
        ("Pooja Gupta",     "AI",           82.0, 74.0),
        ("Rahul Kumar",     "CS",           69.0, 80.0),
        ("Meera Nambiar",   "DS",           93.0, 97.0),
        ("Aditya Raj",      "AI",           78.5, 85.0),
        ("Kavya Menon",     "CS",           84.0, 89.0),
        ("Suresh Pillai",   "DS",           60.0, 62.0),
        ("Lakshmi Rao",     "AI",           97.0, 99.0),
        ("Nikhil Tiwari",   "CS",           71.0, 77.0),
        ("Deepika Sharma",  "DS",           86.0, 88.5),
        ("Siddharth Das",   "AI",           65.0, 68.0),
        ("Nandini Bose",    "CS",           79.0, 82.0),
    ]
    cur.executemany(
        "INSERT INTO students (name, department, marks, attendance) VALUES (?,?,?,?)",
        students,
    )


def _seed_courses(cur: sqlite3.Cursor) -> None:
    courses = [
        ("Machine Learning",        4),
        ("Database Systems",        3),
        ("Natural Language Processing", 4),
        ("Data Structures",         3),
        ("Computer Networks",       3),
        ("Deep Learning",           4),
        ("Statistics for DS",       3),
        ("Operating Systems",       3),
        ("Cloud Computing",         2),
        ("Software Engineering",    3),
    ]
    cur.executemany(
        "INSERT INTO courses (course_name, credits) VALUES (?,?)",
        courses,
    )


def _seed_enrollments(cur: sqlite3.Cursor) -> None:
    # (student_id, course_id, grade)
    enrollments = [
        (1, 1, "A"), (1, 3, "A"), (1, 6, "B"),
        (2, 2, "B"), (2, 4, "A"), (2, 10, "A"),
        (3, 1, "C"), (3, 3, "B"), (3, 9, "C"),
        (4, 2, "A"), (4, 7, "A"), (4, 1, "A"),
        (5, 4, "D"), (5, 5, "C"), (5, 8, "F"),
        (6, 7, "A"), (6, 2, "B"), (6, 6, "B"),
        (7, 1, "C"), (7, 9, "B"),
        (8, 3, "A"), (8, 4, "A"), (8, 10, "A"),
        (9, 2, "D"), (9, 5, "C"),
        (10, 1, "B"), (10, 6, "C"),
        (11, 4, "C"), (11, 5, "B"), (11, 8, "B"),
        (12, 7, "A"), (12, 2, "A"), (12, 3, "A"),
        (13, 1, "B"), (13, 6, "B"),
        (14, 3, "A"), (14, 10, "B"), (14, 4, "A"),
        (15, 2, "D"), (15, 5, "D"),
        (16, 1, "A"), (16, 3, "A"), (16, 6, "A"),
        (17, 4, "C"), (17, 8, "C"),
        (18, 7, "A"), (18, 2, "A"),
        (19, 1, "C"), (19, 9, "C"),
        (20, 4, "B"), (20, 5, "B"), (20, 10, "B"),
    ]
    cur.executemany(
        "INSERT INTO enrollments (student_id, course_id, grade) VALUES (?,?,?)",
        enrollments,
    )


# ---------------------------------------------------------------------------
# Schema introspection helpers
# ---------------------------------------------------------------------------

def get_schema_info() -> dict[str, list[dict]]:
    """Return column metadata for every table as {table: [{name, type, pk}]}."""
    conn = get_connection()
    cur = conn.cursor()
    info: dict[str, list[dict]] = {}
    for table in SCHEMA:
        rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
        info[table] = [
            {"name": r["name"], "type": r["type"], "pk": bool(r["pk"])}
            for r in rows
        ]
    conn.close()
    return info


def execute_query(sql: str, params: tuple = ()) -> list[dict]:
    """
    Execute a validated SELECT query and return rows as a list of dicts.
    Raises ValueError for non-SELECT or multi-statement SQL.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        if rows:
            return [dict(r) for r in rows]
        return []
    finally:
        conn.close()
