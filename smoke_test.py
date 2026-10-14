"""
smoke_test.py  -  Quick functional verification (no pytest needed)
Run:  python smoke_test.py
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from nlp_processor import parse_question
from sql_generator import generate_sql
from sql_validator import validate_sql, contains_injection_pattern

PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  [PASS]  {label}")
        PASS += 1
    else:
        print(f"  [FAIL]  {label}  <- {detail}")
        FAIL += 1

print("\n=== NLP + SQL Generation ===")
cases = [
    "Show all students",
    "Find students who scored more than 80 marks",
    "Show the top 5 students by marks",
    "Count the number of students in each department",
    "Calculate the average marks of students",
    "Find students whose attendance is below 75",
    "Show students from the AI department",
    "List students with their enrolled course names",
    "Find the highest and lowest marks",
    "Show courses with more than 3 credits",
]

for q in cases:
    pq  = parse_question(q)
    gen = generate_sql(pq)
    val = validate_sql(gen.sql) if not gen.error else None
    ok  = (gen.error is None) and (val is not None) and val.is_valid
    detail = gen.error or (val.error if val else "")
    check(repr(q), ok, detail)
    if ok:
        short = gen.sql.replace("\n", " ")
        print(f"       → {short[:90]}{'...' if len(short)>90 else ''}")

print("\n=== Injection Guard ===")
injection_cases = [
    "'; DROP TABLE students; --",
    "1 OR 1=1",
    "UNION SELECT * FROM students",
    "SLEEP(5)",
    "BENCHMARK(1000000, MD5(1))",
]
for p in injection_cases:
    check(f"Blocked: {p!r}", contains_injection_pattern(p))

check("Safe: 'Show all students'",
      not contains_injection_pattern("Show all students"))

print("\n=== SQL Validator – Destructive SQL ===")
bad = [
    "DROP TABLE students;",
    "INSERT INTO students VALUES (1,'x','AI',99,99);",
    "UPDATE students SET marks=100;",
    "DELETE FROM students;",
    "ALTER TABLE students ADD x TEXT;",
    "CREATE TABLE evil (id INT);",
]
for sql in bad:
    r = validate_sql(sql)
    check(f"Blocked: {sql!r}", not r.is_valid)

print("\n=== SQL Validator – Multi-statement ===")
r = validate_sql("SELECT * FROM students; DROP TABLE students;")
check("Multi-statement rejected", not r.is_valid)

r = validate_sql("SELECT * FROM students; SELECT * FROM courses;")
check("Two SELECT statements rejected", not r.is_valid)

print("\n=== SQL Validator – Unknown Table ===")
r = validate_sql("SELECT * FROM secrets;")
check("Unknown table rejected", not r.is_valid)

print("\n=== SQL Validator – Valid SELECT ===")
r = validate_sql("SELECT * FROM students;")
check("Simple SELECT accepted", r.is_valid)

r = validate_sql(
    "SELECT students.name, courses.course_name "
    "FROM students "
    "JOIN enrollments ON students.student_id = enrollments.student_id "
    "JOIN courses ON enrollments.course_id = courses.course_id;"
)
check("3-table JOIN accepted", r.is_valid)

print("\n=== Database Initialisation ===")
try:
    from database import initialize_database, execute_query
    initialize_database()
    rows = execute_query("SELECT COUNT(*) AS cnt FROM students;")
    cnt  = rows[0]["cnt"]
    check(f"DB seeded with {cnt} students (expect >= 15)", cnt >= 15)

    rows = execute_query("SELECT COUNT(*) AS cnt FROM courses;")
    check(f"DB has {rows[0]['cnt']} courses (expect >= 10)", rows[0]["cnt"] >= 10)

    rows = execute_query("SELECT COUNT(*) AS cnt FROM enrollments;")
    check(f"DB has {rows[0]['cnt']} enrollments (expect >= 20)", rows[0]["cnt"] >= 20)
except Exception as e:
    check(f"DB initialisation", False, str(e))

print("\n=== End-to-end Query Test ===")
try:
    q = "Show the top 5 students by marks"
    pq  = parse_question(q)
    gen = generate_sql(pq)
    val = validate_sql(gen.sql)
    rows = execute_query(val.clean_sql, gen.params)
    check(f"Top-5 query returns rows", len(rows) > 0)
    check(f"Top-5 query returns <= 5 rows", len(rows) <= 5)

    q2 = "Count the number of students in each department"
    pq2  = parse_question(q2)
    gen2 = generate_sql(pq2)
    val2 = validate_sql(gen2.sql)
    rows2 = execute_query(val2.clean_sql, gen2.params)
    check(f"Count-per-dept returns groups", len(rows2) >= 1)
except Exception as e:
    check("End-to-end query", False, str(e))

print(f"\n{'='*50}")
print(f"  TOTAL: {PASS} passed, {FAIL} failed")
print(f"{'='*50}\n")
sys.exit(0 if FAIL == 0 else 1)
