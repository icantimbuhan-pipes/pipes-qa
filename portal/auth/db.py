"""Auth & RBAC database layer."""
from datetime import datetime
from typing import Optional

import sqlite3
from werkzeug.security import generate_password_hash

from portal.db import _conn

# ── Seed data ─────────────────────────────────────────────────────────────────

SEED_ROLES = [
    ("Admin",   "Full access — bypasses all permission checks",    1),
    ("Manager", "Most features, no admin panel",                   1),
    ("QA",      "QA runs, validator, QA testing assistant",        1),
    ("Viewer",  "Read-only — dashboard and daily QA only",         1),
]

SEED_PAGES = [
    ("dashboard",    "Dashboard",          "/",             "📊", 0),
    ("daily_qa",     "Daily QA",           "/daily-qa",     "✅", 1),
    ("hourly_qa",    "Hourly QA",          "/daily-qa",     "⏱",  2),
    ("quick_report", "Quick Report",       "/quick-report", "📤", 3),
    ("checklists",   "Checklists",         "/checklists",   "📋", 4),
    ("api_configs",  "API Configs",        "/api-configs",  "🔑", 5),
    ("sms",          "SMS Deliverability", "/upload",       "💬", 6),
    ("dnc",          "DNC Portal",         "/dnc",          "🚫", 7),
    ("validator",    "Validator",          "/validator",    "🧪", 8),
    ("maintenance",  "Maintenance",        "/maintenance",  "⚙",  9),
    ("qa_test",      "QA Testing",         "/qa-test",      "🔍", 10),
    ("admin",        "Admin Panel",        "/admin",        "👤", 11),
]

DEFAULT_PERMISSIONS: dict[str, list[str]] = {
    "Manager": [
        "dashboard", "daily_qa", "hourly_qa", "quick_report",
        "checklists", "api_configs", "sms", "dnc", "validator", "qa_test",
    ],
    "QA": [
        "dashboard", "daily_qa", "hourly_qa", "quick_report", "validator", "qa_test",
    ],
    "Viewer": ["dashboard", "daily_qa"],
}


# ── Init ──────────────────────────────────────────────────────────────────────

def init_auth():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                is_system   INTEGER DEFAULT 0,
                created_at  TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT UNIQUE NOT NULL,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role_id       INTEGER REFERENCES roles(id),
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT NOT NULL,
                last_login    TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key         TEXT UNIQUE NOT NULL,
                name        TEXT NOT NULL,
                url_prefix  TEXT DEFAULT '',
                icon        TEXT DEFAULT '',
                sort_order  INTEGER DEFAULT 0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id    INTEGER REFERENCES roles(id),
                page_id    INTEGER REFERENCES pages(id),
                can_view   INTEGER DEFAULT 0,
                can_edit   INTEGER DEFAULT 0,
                can_delete INTEGER DEFAULT 0,
                is_admin   INTEGER DEFAULT 0,
                PRIMARY KEY (role_id, page_id)
            )
        """)
        _seed(con)


def _seed(con):
    now = datetime.now().isoformat()
    for name, desc, is_system in SEED_ROLES:
        con.execute(
            "INSERT OR IGNORE INTO roles(name,description,is_system,created_at) VALUES(?,?,?,?)",
            (name, desc, is_system, now),
        )
    for key, name, url_prefix, icon, sort_order in SEED_PAGES:
        con.execute(
            "INSERT OR IGNORE INTO pages(key,name,url_prefix,icon,sort_order) VALUES(?,?,?,?,?)",
            (key, name, url_prefix, icon, sort_order),
        )
    for role_name, page_keys in DEFAULT_PERMISSIONS.items():
        role = con.execute("SELECT id FROM roles WHERE name=?", (role_name,)).fetchone()
        if not role:
            continue
        for pk in page_keys:
            page = con.execute("SELECT id FROM pages WHERE key=?", (pk,)).fetchone()
            if page:
                con.execute(
                    "INSERT OR IGNORE INTO role_permissions(role_id,page_id,can_view) VALUES(?,?,1)",
                    (role["id"], page["id"]),
                )
    # Default admin user (only if no users exist)
    if not con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        admin_role = con.execute("SELECT id FROM roles WHERE name='Admin'").fetchone()
        if admin_role:
            con.execute(
                """INSERT INTO users(email,username,password_hash,role_id,is_active,created_at)
                   VALUES(?,?,?,?,1,?)""",
                ("admin@pipes.ai", "admin", generate_password_hash("admin123"),
                 admin_role["id"], now),
            )


# ── Auth queries ──────────────────────────────────────────────────────────────

def get_user_permissions(role_id: int) -> set[str]:
    """Return set of page_keys the role can view."""
    if role_id is None:
        return set()
    with _conn() as con:
        rows = con.execute(
            """SELECT p.key FROM role_permissions rp
               JOIN pages p ON p.id = rp.page_id
               WHERE rp.role_id=? AND rp.can_view=1""",
            (role_id,),
        ).fetchall()
        return {r["key"] for r in rows}


def get_user_row(identifier: str) -> Optional[sqlite3.Row]:
    """Find user by email or username (case-insensitive)."""
    with _conn() as con:
        return con.execute(
            """SELECT u.*, r.name as role_name
               FROM users u LEFT JOIN roles r ON r.id=u.role_id
               WHERE LOWER(u.email)=LOWER(?) OR LOWER(u.username)=LOWER(?)""",
            (identifier, identifier),
        ).fetchone()


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            """SELECT u.*, r.name as role_name
               FROM users u LEFT JOIN roles r ON r.id=u.role_id
               WHERE u.id=?""",
            (user_id,),
        ).fetchone()


def update_last_login(user_id: int):
    with _conn() as con:
        con.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (datetime.now().isoformat(), user_id),
        )


# ── User management ───────────────────────────────────────────────────────────

def list_users():
    with _conn() as con:
        return con.execute(
            """SELECT u.*, r.name as role_name
               FROM users u LEFT JOIN roles r ON r.id=u.role_id
               ORDER BY u.created_at DESC"""
        ).fetchall()


def create_user(email: str, username: str, password: str,
                role_id: int, is_active: bool = True):
    now = datetime.now().isoformat()
    with _conn() as con:
        con.execute(
            """INSERT INTO users(email,username,password_hash,role_id,is_active,created_at)
               VALUES(?,?,?,?,?,?)""",
            (email.lower().strip(), username.strip(),
             generate_password_hash(password), role_id, int(is_active), now),
        )


def update_user(user_id: int, email: str, username: str,
                role_id: int, is_active: bool, password: Optional[str] = None):
    with _conn() as con:
        if password:
            con.execute(
                """UPDATE users SET email=?,username=?,role_id=?,is_active=?,password_hash=?
                   WHERE id=?""",
                (email.lower().strip(), username.strip(), role_id,
                 int(is_active), generate_password_hash(password), user_id),
            )
        else:
            con.execute(
                "UPDATE users SET email=?,username=?,role_id=?,is_active=? WHERE id=?",
                (email.lower().strip(), username.strip(),
                 role_id, int(is_active), user_id),
            )


def delete_user(user_id: int):
    with _conn() as con:
        con.execute("DELETE FROM users WHERE id=?", (user_id,))


# ── Role management ───────────────────────────────────────────────────────────

def list_roles():
    with _conn() as con:
        return con.execute("SELECT * FROM roles ORDER BY id").fetchall()


def get_role(role_id: int) -> Optional[sqlite3.Row]:
    with _conn() as con:
        return con.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()


def create_role(name: str, description: str):
    now = datetime.now().isoformat()
    with _conn() as con:
        con.execute(
            "INSERT INTO roles(name,description,is_system,created_at) VALUES(?,?,0,?)",
            (name.strip(), description.strip(), now),
        )


def delete_role(role_id: int):
    with _conn() as con:
        con.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
        con.execute("DELETE FROM roles WHERE id=? AND is_system=0", (role_id,))


# ── Permission management ─────────────────────────────────────────────────────

def list_pages():
    with _conn() as con:
        return con.execute("SELECT * FROM pages ORDER BY sort_order").fetchall()


def get_all_permissions() -> dict:
    """Return {role_id: {page_id: {can_view, can_edit, can_delete, is_admin}}}"""
    with _conn() as con:
        rows = con.execute("SELECT * FROM role_permissions").fetchall()
        result: dict = {}
        for r in rows:
            result.setdefault(r["role_id"], {})[r["page_id"]] = {
                "can_view":   bool(r["can_view"]),
                "can_edit":   bool(r["can_edit"]),
                "can_delete": bool(r["can_delete"]),
                "is_admin":   bool(r["is_admin"]),
            }
        return result


def save_permissions(role_id: int, permissions: dict):
    """permissions: {page_id: {can_view, can_edit, can_delete, is_admin}}"""
    with _conn() as con:
        con.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
        for page_id, perms in permissions.items():
            con.execute(
                """INSERT INTO role_permissions(role_id,page_id,can_view,can_edit,can_delete,is_admin)
                   VALUES(?,?,?,?,?,?)""",
                (role_id, int(page_id),
                 int(perms.get("can_view", 0)),
                 int(perms.get("can_edit", 0)),
                 int(perms.get("can_delete", 0)),
                 int(perms.get("is_admin", 0))),
            )
