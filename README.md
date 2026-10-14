# 🔍 NL → SQL: Natural Language to SQL Query Generator

A complete, college-level NLP course project that converts plain-English questions into SQL queries, executes them against a local SQLite database, and displays the results — all in a polished Streamlit web interface.

---

## 📌 Problem Statement

Writing SQL requires knowledge of database syntax and schema structure. Non-technical users often cannot query databases directly. This project bridges that gap by allowing users to ask questions in everyday English and automatically generating the correct SQL query.

---

## 🎯 Objectives

- Accept natural-language questions from a web interface.
- Parse and understand the question using an NLP pipeline.
- Generate safe, parameterised SQL queries from the parsed structure.
- Execute the query against a local SQLite database.
- Display results in a readable table with explanations.
- Enforce strict SQL safety rules (no write operations, injection prevention).

---

## ✨ Main Features

| Feature | Details |
|---|---|
| Natural-language input | Free-text question box with sample question buttons |
| Schema-aware parsing | Understands table/column names, filters, sorts, aggregates |
| SQL generation | Parameterised SELECT queries with WHERE, ORDER BY, LIMIT, GROUP BY, JOIN |
| Safety validation | SELECT-only, blocks DROP/INSERT/UPDATE/DELETE/ALTER/CREATE etc. |
| Injection detection | Heuristic guard on raw user input |
| Results table | Pandas DataFrame rendered in the UI with CSV download |
| Plain-English explanation | Each generated query is explained in simple terms |
| Schema viewer | Sidebar shows all tables and columns |
| Automated tests | pytest suite for NLP, SQL generation, and validation |

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Web interface | Streamlit |
| Database | SQLite (via `sqlite3` stdlib) |
| Data display | Pandas |
| NLP / parsing | Regex + rule-based Python (no API, no GPU) |
| Testing | pytest |
| Environment | python-dotenv |

> **No paid APIs, no GPU, no large model downloads required.** The application runs fully offline on a normal laptop.

---

## 🏗️ Architecture & Workflow

```
User Question (English)
        │
        ▼
 ┌──────────────┐
 │ nlp_processor│  ← normalise → detect tables/columns/filters/aggregates/join
 └──────┬───────┘
        │  ParsedQuery
        ▼
 ┌──────────────┐
 │ sql_generator│  ← build SELECT / AGGREGATE SQL + plain-English explanation
 └──────┬───────┘
        │  GeneratedQuery (sql, params, explanation)
        ▼
 ┌──────────────┐
 │ sql_validator│  ← SELECT-only? No forbidden keywords? No multi-statement?
 └──────┬───────┘
        │  ValidationResult (is_valid, clean_sql)
        ▼
 ┌──────────────┐
 │  database.py │  ← execute_query(clean_sql, params) against SQLite
 └──────┬───────┘
        │  List[dict] rows
        ▼
 ┌──────────────┐
 │    app.py    │  ← display results as Pandas DataFrame in Streamlit
 └──────────────┘
```

---

## 📁 Project Structure

```
natural-language-to-sql/
├── app.py                  # Streamlit web application
├── database.py             # DB init, schema constants, query execution
├── nlp_processor.py        # NLP pipeline → ParsedQuery dataclass
├── sql_generator.py        # ParsedQuery → SQL + explanation
├── sql_validator.py        # Safety validation layer
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── .gitignore              # Files excluded from Git
├── .env.example            # Environment variable template (no secrets)
├── data/
│   └── .gitkeep            # Placeholder (school.db created at runtime)
└── tests/
    ├── __init__.py
    ├── test_nlp_processor.py
    ├── test_sql_generator.py
    └── test_sql_validator.py
```

---

## 🚀 Installation & Setup

### Prerequisites

- Python 3.11 or later
- pip

### 1 – Clone / download the repository

```bash
git clone https://github.com/<your-username>/natural-language-to-sql.git
cd natural-language-to-sql
```

### 2 – Create and activate a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3 – Install dependencies

```bash
pip install -r requirements.txt
```

### 4 – (Optional) Configure environment

```bash
cp .env.example .env
# Edit .env if you want to add an OpenAI API key for LLM fallback
```

---

## ▶️ Running the Application

```bash
streamlit run app.py
```

The application will open automatically in your browser at **http://localhost:8501**.

The SQLite database (`data/school.db`) is created and seeded **automatically** on first run — no manual setup needed.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

All tests should pass. To see a coverage summary:

```bash
pip install pytest-cov
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## 💬 Example Questions & Expected Behaviour

| Question | What it does |
|---|---|
| Show all students | `SELECT students.* FROM students;` |
| Find students who scored more than 80 marks | `WHERE marks > 80` |
| Show the top 5 students by marks | `ORDER BY marks DESC LIMIT 5` |
| Count the number of students in each department | `COUNT(*) … GROUP BY department` |
| Calculate the average marks of students | `AVG(marks)` |
| Find students whose attendance is below 75 | `WHERE attendance < 75` |
| Show students from the AI department | `WHERE department = 'AI'` |
| List students with their enrolled course names | 3-table JOIN |
| Find the highest and lowest marks | `MAX(marks), MIN(marks)` |
| Show courses with more than 3 credits | `WHERE credits > 3` |
| Count students in each department | `COUNT(*) GROUP BY department` |
| Find students with grade A | `WHERE grade = 'A'` |
| Show top 3 students by marks | `ORDER BY marks DESC LIMIT 3` |

---

## 🔐 SQL Safety Mechanisms

1. **SELECT-only enforcement** – Any query not starting with `SELECT` is rejected immediately.
2. **Forbidden keyword blocking** – `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `DETACH`, `TRUNCATE`, `EXEC`, `GRANT`, `REVOKE` are all blocked (case-insensitive).
3. **Multi-statement rejection** – A semicolon inside the query (before the trailing one) is rejected.
4. **Table whitelist** – Only `students`, `courses`, `enrollments` are allowed in `FROM`/`JOIN` clauses.
5. **Injection heuristics** – Patterns like `OR '1'='1'`, `UNION SELECT`, `--` comments, `SLEEP()`, `BENCHMARK()` are detected in raw user input before any SQL is generated.
6. **Parameterised queries** – All filter values are passed as `?` parameters, never interpolated into the SQL string.
7. **No direct user SQL** – The user types English; no raw SQL ever reaches the database engine.

---

## ⚠️ Limitations of the Rule-Based Baseline

- **Fixed vocabulary** – Only recognised keywords and phrases trigger correct parsing. Novel phrasing may be misunderstood.
- **Schema-bound** – Only the three predefined tables are supported.
- **No semantic understanding** – "Who performed best?" works; highly paraphrased equivalents may not.
- **Single-language** – English only.
- **No sub-queries** – Nested SELECT statements are not generated.
- **No HAVING clause** – Aggregate filtering after GROUP BY is not yet implemented.

---

## 🔭 Future Enhancements

- Integrate an LLM (via the `OPENAI_API_KEY` env var) as a fallback for unsupported questions.
- Add a HAVING clause for filtered aggregates.
- Support sub-queries and more complex joins.
- Add a user-uploadable schema feature (custom databases).
- Build a REST API layer (FastAPI) so the engine can be called programmatically.
- Add multilingual support.
- Train a seq2seq or fine-tuned model on the Spider dataset for broader coverage.

---

## 📤 GitHub Upload Instructions

```bash
# 1. Initialise Git (if not already done)
git init

# 2. Stage all project files
git add .

# 3. Commit
git commit -m "Initial commit: NL-to-SQL Query Generator"

# 4. Create a new repository on GitHub (via the website), then:
git remote add origin https://github.com/<your-username>/natural-language-to-sql.git
git branch -M main
git push -u origin main
```

> ⚠️ Never commit your `.env` file (it is in `.gitignore`). Only commit `.env.example`.

---

## 📚 NLP Pipeline — Simple Explanation for Viva

> *"How does the system understand English?"*

1. **Normalisation** – The input is lower-cased and contractions like *"who's"* are expanded to *"who is"*. Punctuation is stripped so only meaningful words remain.

2. **Table detection** – A dictionary maps words like *"student"*, *"course"*, *"enrolled"* to their database table names. If no table is mentioned, `students` is assumed.

3. **Intent detection** – Keywords like *"count"*, *"average"*, *"top N"*, *"sort"* tell us whether to build a plain `SELECT`, a `COUNT(*)`, or an aggregate (`AVG`, `MAX`, `MIN`).

4. **Filter extraction** – Regular expressions find comparison phrases like *"more than 80"* or *"below 75%"* and convert them to `WHERE` clause conditions with the correct operator (`>`, `<`, `>=`, etc.).

5. **Group-by detection** – Phrases like *"in each department"* or *"per department"* trigger a `GROUP BY department`.

6. **Join detection** – Phrases like *"with their course names"* flag that a multi-table join is needed.

7. **SQL assembly** – All detected parts are assembled into a parameterised SQL string with `?` placeholders for values.

8. **Safety validation** – The generated SQL is checked: only `SELECT` is allowed; forbidden keywords, unknown tables, and multi-statement queries are blocked.

9. **Execution** – The validated query runs against the local SQLite database and results are shown in the UI.

---

## 👨‍💻 Author

College NLP Course Project  
Built with Python 3 · Streamlit · SQLite · Pandas · pytest
