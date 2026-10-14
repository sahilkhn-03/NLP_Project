"""
api/index.py
------------
Vercel Serverless Function entry point for the NL-to-SQL engine.
Serves:
  POST /api/query   - Process plain-English question into SQL & execute it
  GET  /api/schema  - Return database tables & column metadata
  GET  /api/samples - Return categorized sample questions
  GET  /api/stats   - Return record counts
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure project root is in sys.path so modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import initialize_database, execute_query, get_schema_info
from nlp_processor import parse_question
from sql_generator import generate_sql
from sql_validator import validate_sql, contains_injection_pattern

# Ensure database is initialized once per serverless instance
try:
    initialize_database()
except Exception:
    pass

CATEGORIZED_SAMPLES = [
    {"category": "📋 Basic",     "question": "Show all students"},
    {"category": "📋 Basic",     "question": "List all courses"},
    {"category": "🔍 Filter",    "question": "Find students who scored more than 80 marks"},
    {"category": "🔍 Filter",    "question": "Find students whose attendance is below 75"},
    {"category": "🔍 Filter",    "question": "Show students from the AI department"},
    {"category": "🔍 Filter",    "question": "Show students from the CS department"},
    {"category": "🔍 Filter",    "question": "Show courses with more than 3 credits"},
    {"category": "🔍 Filter",    "question": "Find students with grade A"},
    {"category": "📊 Ranking",   "question": "Show the top 5 students by marks"},
    {"category": "📊 Ranking",   "question": "Show top 3 students by marks"},
    {"category": "📊 Ranking",   "question": "Find students with attendance above 90"},
    {"category": "📈 Aggregate", "question": "Count the number of students in each department"},
    {"category": "📈 Aggregate", "question": "Calculate the average marks of students"},
    {"category": "📈 Aggregate", "question": "Find the highest and lowest marks"},
    {"category": "📈 Aggregate", "question": "Count total number of students"},
    {"category": "📈 Aggregate", "question": "What is the average attendance?"},
    {"category": "🔗 Join",      "question": "List students with their enrolled course names"},
]


class handler(BaseHTTPRequestHandler):
    """Vercel Python serverless HTTP handler."""

    def _send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _resolve_endpoint(self) -> str:
        """Extract the intended target endpoint despite Vercel rewrite variations."""
        parsed_url = urlparse(self.path)

        # 1. Query parameter check (e.g. /api/index.py?endpoint=schema)
        qs = parse_qs(parsed_url.query)
        for param in ("endpoint", "action", "path"):
            if param in qs and qs[param]:
                val = qs[param][0].strip("/").lower()
                if val:
                    return val

        # 2. Vercel routing headers
        for hdr in ("x-matched-path", "x-forwarded-uri", "x-rewrite-url", "x-original-url"):
            val = self.headers.get(hdr)
            if val and "index.py" not in val:
                clean = urlparse(val).path.strip("/").lower()
                if clean.startswith("api/"):
                    clean = clean[4:]
                if clean:
                    return clean

        # 3. Path inspection
        clean_path = parsed_url.path.strip("/").lower()
        if clean_path.startswith("api/"):
            clean_path = clean_path[4:]
        if clean_path.endswith("index.py"):
            clean_path = clean_path[:-8].rstrip("/")

        return clean_path

    def do_GET(self) -> None:
        ep = self._resolve_endpoint()

        # Samples
        if "sample" in ep:
            self._send_json(200, {"samples": CATEGORIZED_SAMPLES})
            return

        # Schema info
        if "schema" in ep:
            try:
                schema = get_schema_info()
                self._send_json(200, {"schema": schema})
            except Exception as exc:
                self._send_json(500, {"error": f"Failed to retrieve schema: {exc}"})
            return

        # Database Stats
        if "stat" in ep:
            try:
                students = execute_query("SELECT COUNT(*) AS c FROM students;")[0]["c"]
                courses = execute_query("SELECT COUNT(*) AS c FROM courses;")[0]["c"]
                enrollments = execute_query("SELECT COUNT(*) AS c FROM enrollments;")[0]["c"]
                self._send_json(200, {
                    "students": students,
                    "courses": courses,
                    "enrollments": enrollments,
                })
            except Exception as exc:
                self._send_json(500, {"error": f"Failed to retrieve stats: {exc}"})
            return

        # Default fallback for GET: return all metadata at once
        try:
            schema = get_schema_info()
        except Exception:
            schema = {}

        try:
            students = execute_query("SELECT COUNT(*) AS c FROM students;")[0]["c"]
            courses = execute_query("SELECT COUNT(*) AS c FROM courses;")[0]["c"]
            enrollments = execute_query("SELECT COUNT(*) AS c FROM enrollments;")[0]["c"]
        except Exception:
            students, courses, enrollments = 20, 10, 52

        self._send_json(200, {
            "status": "ok",
            "service": "NL-to-SQL API",
            "schema": schema,
            "samples": CATEGORIZED_SAMPLES,
            "students": students,
            "courses": courses,
            "enrollments": enrollments,
        })

    def do_POST(self) -> None:
        # On Vercel, ANY POST to this serverless function is a query generation request.
        # This completely avoids 404s caused by Vercel rewrite path differences.
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            self._send_json(400, {"error": "Empty request body"})
            return

        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        question = (payload.get("question") or "").strip()
        if not question:
            self._send_json(400, {"error": "Please provide a 'question' string."})
            return

        if len(question) > 500:
            self._send_json(400, {"error": "Question is too long (maximum 500 characters)."})
            return

        if contains_injection_pattern(question):
            self._send_json(400, {
                "error": "Input contains forbidden characters or SQL injection patterns."
            })
            return

        # NLP Parse
        try:
            parsed = parse_question(question)
        except Exception as exc:
            self._send_json(500, {"error": f"NLP parser failed: {exc}"})
            return

        if parsed.error:
            self._send_json(422, {"error": parsed.error})
            return

        # SQL Generation
        try:
            gen = generate_sql(parsed)
        except Exception as exc:
            self._send_json(500, {"error": f"SQL generation failed: {exc}"})
            return

        if gen.error:
            self._send_json(422, {"error": gen.error})
            return

        # Validation
        try:
            val = validate_sql(gen.sql)
        except Exception as exc:
            self._send_json(500, {"error": f"Security validation failed: {exc}"})
            return

        if not val.is_valid:
            self._send_json(403, {"error": f"Security check failed: {val.error}"})
            return

        # Safe Execution
        t0 = time.perf_counter()
        try:
            rows = execute_query(val.clean_sql, gen.params)
        except Exception as exc:
            self._send_json(500, {"error": f"Database execution failed: {exc}"})
            return

        exec_time_ms = round((time.perf_counter() - t0) * 1000, 2)
        columns = list(rows[0].keys()) if rows else []

        self._send_json(200, {
            "success": True,
            "question": question,
            "sql": val.clean_sql,
            "explanation": gen.explanation,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "exec_time_ms": exec_time_ms,
        })
