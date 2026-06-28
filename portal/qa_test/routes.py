"""QA Testing Assistant — multi-backend AI analysis (Groq / Ollama / Anthropic)."""
import base64
import os
import re
from typing import Optional

import httpx
from dotenv import load_dotenv
from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from portal.db import delete_qa_run, get_qa_run, list_qa_runs, save_qa_run

load_dotenv()

bp = Blueprint("qa_test", __name__, template_folder="templates")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"

BACKEND_LABELS = {
    "anthropic": "Claude (Anthropic)",
    "groq":      "Groq · LLaMA (free)",
    "ollama":    "Ollama · local (free)",
}

SYSTEM_PROMPT = """You are a senior QA engineer. Analyze the evidence provided, validate expected behavior, identify defects, and generate structured findings with supporting proof.

Your responsibilities:
1. Requirement Validation — compare implementation against requirements; flag missing, incorrect, or unexpected behavior
2. UI Validation — labels, buttons, table headers, sorting, filtering, pagination, visibility, alignment, data consistency
3. Export Validation — verify UI table columns match CSV/Excel download columns (see detailed rules below)
4. API Validation — status codes, response structure, required fields, data accuracy, error handling
5. Database Validation — data persistence, integrity, duplicate handling, record relationships
6. Log & Error Analysis — console errors, backend logs, warnings, performance issues
7. Root Cause Investigation — suggest causes for failures when evidence supports it

── EXPORT VALIDATION — Header Comparison Rules ──────────────────────────────

When comparing UI table headers against CSV column headers, follow these steps exactly:

STEP 1 — Expand grouped UI headers
  UI tables often group related columns into one display header using notation like:
    "Parameters(Response>Status)"  →  means 3 separate columns: Parameters, Response, Status
    "Col1 / Col2"                  →  means 2 separate columns: Col1, Col2
    "Name (First/Last)"            →  means the column shows both First and Last name
  Expand all grouped headers before comparing. The "|", "(", ")", ">" characters in a UI
  header label are display separators, not part of the column name itself.

STEP 2 — Normalize both sides before comparing
  - Trim whitespace from every header name
  - Comparison is case-insensitive ("Phone Number" == "phone number")
  - Ignore parenthetical display hints: "Date (UTC)" == "Date"

STEP 3 — Check each expanded UI column exists in CSV
  - If a UI column is present in the CSV → ✅ PASS for that column
  - If a UI column is completely absent from the CSV → ❌ FAIL
  - If the CSV has extra columns not shown in the UI → ⚠️ WARNING (extra data exported)

STEP 4 — Report header comparison and data quality SEPARATELY
  Header mismatch = a column name is missing or renamed between UI and CSV.
  Data quality issue = a value inside a cell is wrong, truncated, or malformed.
  NEVER mark a header comparison as FAIL because a data value in a column looks unusual.
  Report each as a distinct finding with its own Status line.

EXAMPLE — correct interpretation:
  UI headers:   Date | Type | Phone Number | Lead | URL | Parameters(Response>Status)
  CSV headers:  Date, Type, Phone Number, Lead, URL, Parameters, Response, Status
  Expanded UI:  Date, Type, Phone Number, Lead, URL, Parameters, Response, Status
  Result:       ✅ PASS — all 8 columns match (UI grouped last 3 for display only)

── MULTI-TABLE COMPARISON ──────────────────────────────────────────────────

When the UI Table Headers field contains multiple tables separated by section labels:

  === Table or Page Name ===
  Header1 | Header2 | Header3

  === Another Table ===
  ColA | ColB | ColC

Follow this process:
1. Split the headers field into separate sections at each "=== ... ===" label.
2. Match each section to its corresponding CSV file by filename similarity.
   - If 2 sections + 2 CSV files: pair them in order (1st section → 1st CSV, 2nd → 2nd).
   - Use the section label to identify which CSV belongs to which table.
3. Run the full header comparison (Steps 1–4 above) independently for each pair.
4. Report a SEPARATE finding block for each table, clearly labeled with the table name.
5. The overall test Result is:
   - PASS  → all tables pass
   - PARTIAL → some pass, some fail
   - FAIL  → all tables fail

─────────────────────────────────────────────────────────────────────────────

Use this format for every issue:

Status: ✅ PASS | ⚠️ WARNING | ❌ FAILED

Issue:
[One sentence describing the problem]

Expected:
[Correct behavior]

Actual:
[Observed behavior]

Evidence:
[Screenshot observation / UI header / CSV column / API field / log line]

Possible Root Cause:
[Only when identifiable from evidence]

Recommendation:
[Specific fix or next step]

---

End with this summary:

─────────────────────────────────
Test Scenario: [Feature or flow tested]
Result: PASS ✅ | FAIL ❌ | PARTIAL ⚠️
─────────────────────────────────
Issues Found:
1. [Brief description] — ❌/⚠️/✅
...

Recommendations:
1. [Action item]
...

Rules:
- You are a QA ANALYST, not a developer. NEVER generate code, scripts, SQL queries, commands, or data manipulation pipelines of any kind.
- Treat ALL code snippets, Python scripts, SQL, or command-line instructions in the evidence as artifacts to REVIEW — check if they look correct for the stated goal. Do NOT rewrite, extend, fix, or debug them.
- When UI Table Headers and CSV files are both present, your PRIMARY task is header comparison (Steps 1–4 above). Run the header check first; all other analysis is secondary.
- Your output is EXCLUSIVELY structured QA findings in the format above. No code, no scripts, nothing else.
- Only report issues supported by the evidence provided.
- Do not assume behavior you cannot see.
- When in doubt, mark ⚠️ WARNING and state what additional evidence is needed.
- If all checks pass, say so explicitly with ✅ PASS and why.
- Header comparison and data value issues are always reported as separate findings."""


# ── Backend detection ─────────────────────────────────────────────────────────

def _detect_backend() -> tuple[Optional[str], dict]:
    """Return (backend_name, config) for the first available AI backend.

    Priority: Anthropic (paid) → Groq (free cloud) → Ollama (free local)
    """
    # 1. Anthropic — set ANTHROPIC_API_KEY in .env
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return "anthropic", {"api_key": key}

    # 2. Groq — free tier at console.groq.com, set GROQ_API_KEY in .env
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        return "groq", {"api_key": key, "model": model}

    # 3. Ollama — local, install from ollama.com, set OLLAMA_MODEL in .env
    url   = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    try:
        r = httpx.get(f"{url}/api/version", timeout=2)
        if r.status_code == 200:
            return "ollama", {"url": url, "model": model}
    except Exception:
        pass

    return None, {}


# ── Content builder ───────────────────────────────────────────────────────────

def _build_content(form, files) -> list:
    """Build content blocks from form inputs and uploaded files."""
    parts: list = []
    text_lines: list = []

    if form.get("feature_name"):
        text_lines.append(f"**Feature:** {form['feature_name']}")
    if form.get("user_story"):
        text_lines.append(f"\n**User Story / Requirements:**\n{form['user_story']}")
    if form.get("test_steps"):
        text_lines.append(f"\n**Test Steps:**\n{form['test_steps']}")
    if form.get("expected"):
        text_lines.append(f"\n**Expected Results:**\n{form['expected']}")
    if form.get("actual"):
        text_lines.append(f"\n**Actual Results:**\n{form['actual']}")
    if form.get("ui_headers"):
        text_lines.append(f"\n**UI Table Headers:**\n{form['ui_headers']}")
    if form.get("api_response"):
        text_lines.append(f"\n**API Response:**\n```json\n{form['api_response']}\n```")
    if form.get("db_records"):
        text_lines.append(f"\n**Database Records:**\n```\n{form['db_records']}\n```")
    if form.get("error_logs"):
        text_lines.append(f"\n**Error Logs / Console Output:**\n```\n{form['error_logs']}\n```")
    if form.get("extra_notes"):
        text_lines.append(f"\n**Additional Notes:**\n{form['extra_notes']}")

    for f in files.getlist("csv_files"):
        if f and f.filename:
            try:
                content = f.read().decode("utf-8", errors="replace")
                text_lines.append(f"\n**CSV File ({f.filename}):**\n```csv\n{content[:4000]}\n```")
            except Exception:
                pass

    if text_lines:
        parts.append({"type": "text", "text": "\n".join(text_lines)})

    for img in files.getlist("screenshots"):
        if img and img.filename:
            try:
                data = img.read()
                b64  = base64.standard_b64encode(data).decode()
                parts.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": img.content_type or "image/png", "data": b64},
                })
                parts.append({"type": "text", "text": f"[Screenshot: {img.filename}]"})
            except Exception:
                pass

    return parts


def _text_only(content: list) -> tuple[str, bool]:
    """Extract plain text from content blocks. Returns (text, had_images)."""
    texts = [c["text"] for c in content if c.get("type") == "text"]
    had_images = any(c.get("type") == "image" for c in content)
    return "\n\n".join(texts), had_images


# ── AI callers ────────────────────────────────────────────────────────────────

def _call_anthropic(api_key: str, content: list) -> str:
    resp = httpx.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": content}],
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Anthropic error {resp.status_code}: {resp.text[:300]}")
    return resp.json()["content"][0]["text"]


def _call_openai_compat(endpoint: str, model: str, api_key: str, content: list) -> str:
    """Generic OpenAI-compatible call — used for Groq and Ollama."""
    user_text, had_images = _text_only(content)
    if had_images:
        user_text += (
            "\n\n[Note: Screenshots were uploaded but cannot be analyzed by this model. "
            "Describe the screenshot content in the 'Actual results' or 'Additional notes' fields "
            "to include that evidence in the analysis.]"
        )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = httpx.post(
        endpoint,
        headers=headers,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_text},
            ],
            "max_tokens": 4096,
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"AI error {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"]


# ── Routes ────────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    backend, config = _detect_backend()
    return render_template("qa_test/index.html",
                           backend=backend,
                           backend_label=BACKEND_LABELS.get(backend or "", ""),
                           has_backend=backend is not None)


@bp.route("/analyze", methods=["POST"])
def analyze():
    backend, config = _detect_backend()
    if not backend:
        return jsonify({"ok": False,
                        "error": "No AI backend configured. See setup options on this page."}), 400

    content = _build_content(request.form, request.files)
    if not content:
        return jsonify({"ok": False, "error": "No evidence provided. Fill in at least one field."}), 400

    try:
        if backend == "anthropic":
            findings = _call_anthropic(config["api_key"], content)

        elif backend == "groq":
            findings = _call_openai_compat(GROQ_URL, config["model"], config["api_key"], content)

        elif backend == "ollama":
            findings = _call_openai_compat(
                f"{config['url']}/v1/chat/completions", config["model"], "", content)

        else:
            return jsonify({"ok": False, "error": "Unknown backend."}), 500

        m = re.search(r'Result:\s*(PASS|FAIL|PARTIAL)', findings, re.IGNORECASE)
        result = m.group(1).upper() if m else "UNKNOWN"
        try:
            run_id = save_qa_run(
                request.form.get("feature_name", "").strip(),
                result, findings, backend)
        except Exception:
            run_id = None

        return jsonify({"ok": True, "findings": findings, "backend": backend,
                        "backend_label": BACKEND_LABELS.get(backend, ""),
                        "run_id": run_id})

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@bp.route("/check-headers", methods=["POST"])
def check_headers():
    """Pure-Python CSV header comparison — no AI needed."""
    import csv as _csv
    import io as _io

    ui_text   = request.form.get("ui_headers", "").strip()
    csv_files = request.files.getlist("csv_files")

    if not ui_text:
        return jsonify({"ok": False, "error": "No UI headers provided."}), 400

    # ── Parse UI header sections ─────────────────────────────────────────────
    tables = []          # list of (name, [normalized_col, ...])
    cur_name = None
    cur_cols = []

    for raw_line in ui_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        sec_m = re.match(r'^===\s*(.+?)\s*===\s*$', line)
        if sec_m:
            if cur_name is not None:
                tables.append((cur_name, cur_cols))
            cur_name = sec_m.group(1).strip()
            cur_cols = []
            continue
        if cur_name is None:
            continue
        # Split by pipe, tab, or 3+ spaces
        parts = re.split(r'\||\t| {3,}', line)
        for part in parts:
            # Expand grouped notation: "Parameters(Response>Status)" → 3 columns
            subs = re.split(r'[()>]', part)
            for s in subs:
                col = re.sub(r'\s*\(.*?\)', '', s).strip()
                if col:
                    cur_cols.append(col.lower())

    if cur_name is not None:
        tables.append((cur_name, cur_cols))

    if not tables:
        return jsonify({"ok": False,
                        "error": "No table sections found. Make sure headers are under "
                                 "a table name (e.g. === Table Name ===)."}), 400

    # ── Parse CSV first rows ─────────────────────────────────────────────────
    csv_data = []
    for f in csv_files:
        if not (f and f.filename):
            continue
        try:
            content = f.read().decode("utf-8", errors="replace")
            reader  = _csv.reader(_io.StringIO(content))
            for row in reader:
                csv_data.append({
                    "filename": f.filename,
                    "cols": [c.strip().lower() for c in row if c.strip()],
                })
                break
        except Exception as exc:
            csv_data.append({"filename": f.filename, "cols": [], "error": str(exc)})

    # ── Compare per table ────────────────────────────────────────────────────
    results = []
    for i, (tname, ui_cols) in enumerate(tables):
        if not ui_cols:
            results.append({"table": tname, "status": "SKIP",
                             "message": "No columns found in UI headers for this table."})
            continue

        if i >= len(csv_data):
            results.append({"table": tname, "status": "SKIP",
                             "message": "No CSV file paired with this table."})
            continue

        info     = csv_data[i]
        csv_cols = info["cols"]
        filename = info["filename"]

        if "error" in info:
            results.append({"table": tname, "status": "ERROR",
                             "filename": filename, "message": info["error"]})
            continue

        missing = [c for c in ui_cols if c not in csv_cols]
        extra   = [c for c in csv_cols if c not in ui_cols]

        if not missing:
            results.append({
                "table": tname, "status": "PASS", "filename": filename,
                "message": f"All {len(ui_cols)} column(s) match.",
                "extra": extra,
            })
        else:
            results.append({
                "table": tname, "status": "FAIL", "filename": filename,
                "message": f"{len(missing)} column(s) missing in CSV.",
                "missing": missing, "extra": extra,
                "ui_cols": ui_cols, "csv_cols": csv_cols,
            })

    statuses = [r["status"] for r in results]
    if all(s == "PASS" for s in statuses):
        overall = "PASS"
    elif any(s == "FAIL" for s in statuses):
        overall = "FAIL"
    else:
        overall = "PARTIAL"

    return jsonify({"ok": True, "results": results, "overall": overall})


@bp.route("/history")
def history():
    runs = list_qa_runs()
    return render_template("qa_test/history.html", runs=runs)


@bp.route("/history/<int:run_id>")
def run_detail(run_id):
    run = get_qa_run(run_id)
    if not run:
        abort(404)
    return render_template("qa_test/run_detail.html", run=run)


@bp.route("/history/<int:run_id>/delete", methods=["POST"])
def delete_run(run_id):
    delete_qa_run(run_id)
    return redirect(url_for("qa_test.history"))


@bp.route("/send-slack", methods=["POST"])
def send_to_slack():
    body     = request.get_json(force=True) or {}
    findings = (body.get("findings") or "").strip()
    feature  = (body.get("feature") or "").strip()

    if not findings:
        return jsonify({"ok": False, "error": "No findings to send."}), 400

    webhook_url = (os.environ.get("SMS_SLACK_WEBHOOK_URL") or
                   os.environ.get("SLACK_WEBHOOK_URL") or "").strip()
    if not webhook_url:
        return jsonify({"ok": False,
                        "error": "No Slack webhook set in .env "
                                 "(SMS_SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL)."}), 400

    title = f"QA Finding — {feature}" if feature else "QA Testing Assistant — Finding"

    # Detect overall result for the header line
    result_m = re.search(r'\bResult:\s*(PASS|FAIL|PARTIAL)', findings)
    if result_m:
        r = result_m.group(1)
        icon  = "✅" if r == "PASS" else ("❌" if r == "FAIL" else "⚠️")
        title = f"{icon} {title} — {r}"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title[:150], "emoji": True}},
        {"type": "divider"},
    ]

    # Split findings into logical paragraphs (split at blank lines or ─── dividers)
    # Each chunk ≤ 2900 chars (Slack section text limit)
    MAX = 2900
    paragraphs = re.split(r'\n{2,}|─{5,}', findings)
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        candidate = (current_chunk + "\n\n" + para).strip() if current_chunk else para
        if len(candidate) <= MAX:
            current_chunk = candidate
        else:
            if current_chunk:
                blocks.append({"type": "section",
                                "text": {"type": "mrkdwn", "text": current_chunk}})
            current_chunk = para[:MAX]

    if current_chunk:
        blocks.append({"type": "section",
                        "text": {"type": "mrkdwn", "text": current_chunk}})

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "via *Pipes.QA Portal* · QA Testing Assistant"}]
    })

    try:
        resp = httpx.post(webhook_url, json={"blocks": blocks}, timeout=10)
        if resp.status_code == 200 and resp.text.strip() == "ok":
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": f"Slack returned: {resp.text[:200]}"}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
