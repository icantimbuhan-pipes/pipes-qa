import json
import os
import re
import uuid

import httpx
from dotenv import dotenv_values
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from portal.db import (
    delete_provider_config, get_all_qa_settings, get_provider_config,
    list_provider_configs, save_provider_config, save_qa_settings,
)

bp = Blueprint("api_configs", __name__, template_folder="templates")

DEFAULT_API_URL = "https://leads.pipes.ai/api/lead"

# All known providers — used to seed the list with empty rows if not yet configured
ALL_PROVIDERS = [
    {"key": "heavy_khomp",         "name": "Heavy Khomp (ThinQ)"},
    {"key": "heavy_khomp_dynamic", "name": "Heavy Khomp Dynamic"},
    {"key": "lite_khomp",          "name": "Lite Khomp"},
    {"key": "tbi_khomp",           "name": "TBI Khomp"},
    {"key": "tbi_fs",              "name": "TBI Freeswitch"},
    {"key": "signalmash_khomp",    "name": "Signalmash Khomp"},
    {"key": "signalmash_fs",       "name": "Signalmash Freeswitch"},
    {"key": "accident_office",     "name": "Accident Office (RetellAI)"},
    {"key": "sms_signalmash",      "name": "SMS Signalmash"},
    {"key": "sms_ai_signalmash",   "name": "SMS AI Signalmash"},
]

# Env var names for each provider (for "load from .env" hint)
_ENV_KEY_MAP = {
    "heavy_khomp":         "HEAVY_KHOMP_API_KEY",
    "heavy_khomp_dynamic": "HEAVY_KHOMP_API_KEY",
    "lite_khomp":          "LITE_KHOMP_API_KEY",
    "tbi_khomp":           "TBI_KHOMP_API_KEY",
    "tbi_fs":              "TBI_FS_API_KEY",
    "signalmash_khomp":    "SIGNALMASH_KHOMP_API_KEY",
    "signalmash_fs":       "SIGNALMASH_FS_API_KEY",
    "accident_office":     "",
    "sms_signalmash":      "SIGNALMASH_SMS_API_KEY",
    "sms_ai_signalmash":   "SIGNALMASH_SMS_AI_API_KEY",
}

QA_SETTING_FIELDS = [
    {"key": "phone_number",   "label": "QA Phone Number",   "placeholder": "e.g. 5122227114",                   "hint": "QA_PHONE_NUMBER"},
    {"key": "ip_address",     "label": "IP Address",        "placeholder": "e.g. 79.116.129.221",               "hint": "QA_IP_ADDRESS"},
    {"key": "email",          "label": "Email",             "placeholder": "e.g. qa@pipes.ai",                  "hint": "QA_EMAIL"},
    {"key": "jornaya_leadid", "label": "Jornaya Lead ID",   "placeholder": "e.g. 93C30C8C-FA4F-D125...",        "hint": "QA_JORNAYA_LEADID"},
]


_KNOWN_KEYS = {p["key"] for p in ALL_PROVIDERS}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _env_val(key: str) -> str:
    """Read current .env value for a key."""
    try:
        return dotenv_values(".env").get(key, "") or ""
    except Exception:
        return ""


def _build_provider_list() -> list:
    """Merge ALL_PROVIDERS with DB configs — always show every provider, plus custom ones."""
    saved = {r["key"]: dict(r) for r in list_provider_configs()}
    env   = dotenv_values(".env")
    result = []

    # Built-in providers first
    for p in ALL_PROVIDERS:
        db = saved.get(p["key"])
        env_key = _ENV_KEY_MAP.get(p["key"], "")
        env_api_key = env.get(env_key, "") if env_key else ""
        result.append({
            "key":         p["key"],
            "name":        db["name"]    if db else p["name"],
            "api_key":     db["api_key"] if db else "",
            "api_url":     db["api_url"] if db else DEFAULT_API_URL,
            "first_name":  db["first_name"] if db else "",
            "last_name":   db["last_name"]  if db else "",
            "state":       db["state"]       if db else "FL",
            "postal_code": db["postal_code"] if db else "32004",
            "configured":  bool(db and db.get("api_key")),
            "env_api_key": env_api_key,
            "env_key":     env_key,
            "custom":      False,
        })

    # Custom providers (DB-only — not in ALL_PROVIDERS)
    for key, db in saved.items():
        if key not in _KNOWN_KEYS:
            result.append({
                "key":         key,
                "name":        db["name"],
                "api_key":     db["api_key"],
                "api_url":     db["api_url"] or DEFAULT_API_URL,
                "first_name":  db["first_name"],
                "last_name":   db["last_name"],
                "state":       db["state"],
                "postal_code": db["postal_code"],
                "configured":  bool(db.get("api_key")),
                "env_api_key": "",
                "env_key":     "",
                "custom":      True,
            })

    return result


@bp.route("/")
def index():
    providers = _build_provider_list()
    qa        = get_all_qa_settings()
    env       = dotenv_values(".env")
    # Fill in env fallbacks for display
    for f in QA_SETTING_FIELDS:
        if f["key"] not in qa:
            qa[f["key"]] = env.get(f["hint"], "")
    return render_template(
        "api_configs/list.html",
        providers=providers,
        qa=qa,
        qa_fields=QA_SETTING_FIELDS,
    )


@bp.route("/new")
def new():
    config = {
        "key":         "",
        "name":        "",
        "api_url":     DEFAULT_API_URL,
        "api_key":     "",
        "first_name":  "",
        "last_name":   "",
        "state":       "FL",
        "postal_code": "32004",
        "extra_json":  "{}",
    }
    return render_template("api_configs/edit.html", config=config, env_key="", is_new=True)


@bp.route("/create", methods=["POST"])
def create():
    name = request.form.get("name", "").strip()
    key  = request.form.get("key",  "").strip()
    if not name:
        flash("Provider name is required.", "error")
        return redirect(url_for("api_configs.new"))
    if not key:
        key = _slug(name)
    if not key:
        flash("Could not generate a key from that name.", "error")
        return redirect(url_for("api_configs.new"))
    # Check for key conflict
    existing = get_provider_config(key)
    if existing:
        flash(f'Key "{key}" already exists. Edit it instead.', "error")
        return redirect(url_for("api_configs.edit", provider_key=key))

    save_provider_config(
        id=          str(uuid.uuid4()),
        key=         key,
        name=        name,
        api_url=     request.form.get("api_url",     DEFAULT_API_URL).strip(),
        api_key=     request.form.get("api_key",     "").strip(),
        first_name=  request.form.get("first_name",  "").strip(),
        last_name=   request.form.get("last_name",   "").strip(),
        state=       request.form.get("state",       "FL").strip(),
        postal_code= request.form.get("postal_code", "32004").strip(),
        extra_json=  request.form.get("extra_json",  "{}").strip() or "{}",
    )
    flash(f'Provider "{name}" created.', "success")
    return redirect(url_for("api_configs.index"))


@bp.route("/<provider_key>/edit")
def edit(provider_key: str):
    p       = next((x for x in ALL_PROVIDERS if x["key"] == provider_key), None)
    db      = get_provider_config(provider_key)
    db      = dict(db) if db else {}
    # Accept custom (DB-only) providers too
    if not p and not db:
        flash("Unknown provider.", "error")
        return redirect(url_for("api_configs.index"))

    env     = dotenv_values(".env")
    env_key = _ENV_KEY_MAP.get(provider_key, "")

    fallback_name = p["name"] if p else provider_key
    config = {
        "key":         provider_key,
        "name":        db.get("name",        fallback_name),
        "api_url":     db.get("api_url",     DEFAULT_API_URL),
        "api_key":     db.get("api_key",     env.get(env_key, "") or ""),
        "first_name":  db.get("first_name",  ""),
        "last_name":   db.get("last_name",   ""),
        "state":       db.get("state",       "FL"),
        "postal_code": db.get("postal_code", "32004"),
        "extra_json":  db.get("extra_json",  "{}"),
    }
    is_custom = provider_key not in _KNOWN_KEYS
    return render_template(
        "api_configs/edit.html",
        config=config,
        env_key=env_key,
        is_new=False,
        is_custom=is_custom,
    )


@bp.route("/<provider_key>/save", methods=["POST"])
def save(provider_key: str):
    p = next((x for x in ALL_PROVIDERS if x["key"] == provider_key), None)
    # Also allow saving custom (DB-only) providers
    if not p and not get_provider_config(provider_key):
        flash("Unknown provider.", "error")
        return redirect(url_for("api_configs.index"))

    fallback_name = p["name"] if p else provider_key
    save_provider_config(
        id=          str(uuid.uuid4()),
        key=         provider_key,
        name=        request.form.get("name",        fallback_name).strip(),
        api_url=     request.form.get("api_url",     DEFAULT_API_URL).strip(),
        api_key=     request.form.get("api_key",     "").strip(),
        first_name=  request.form.get("first_name",  "").strip(),
        last_name=   request.form.get("last_name",   "").strip(),
        state=       request.form.get("state",       "FL").strip(),
        postal_code= request.form.get("postal_code", "32004").strip(),
        extra_json=  request.form.get("extra_json",  "{}").strip() or "{}",
    )
    flash(f"Config for {p['name']} saved.", "success")
    return redirect(url_for("api_configs.index"))


@bp.route("/<provider_key>/delete", methods=["POST"])
def delete(provider_key: str):
    delete_provider_config(provider_key)
    flash("Config deleted — will fall back to .env values.", "success")
    return redirect(url_for("api_configs.index"))


@bp.route("/shared/save", methods=["POST"])
def save_shared():
    settings = {
        f["key"]: request.form.get(f["key"], "").strip()
        for f in QA_SETTING_FIELDS
    }
    save_qa_settings(settings)
    flash("Shared QA settings saved.", "success")
    return redirect(url_for("api_configs.index"))


@bp.route("/<provider_key>/test", methods=["POST"])
def test_api(provider_key: str):
    """Quick test fire — uses DB config (or env fallback). Returns JSON."""
    from datetime import date

    db  = get_provider_config(provider_key)
    db  = dict(db) if db else {}
    qa  = get_all_qa_settings()
    env = dotenv_values(".env")

    def _val(qa_key, env_key, default=""):
        return qa.get(qa_key) or env.get(env_key, "") or default

    env_key = _ENV_KEY_MAP.get(provider_key, "")
    api_key = db.get("api_key") or (env.get(env_key, "") if env_key else "")
    api_url = db.get("api_url") or DEFAULT_API_URL

    params = {
        "phone_number":      _val("phone_number",   "QA_PHONE_NUMBER",   "5122227114"),
        "ip_address":        _val("ip_address",     "QA_IP_ADDRESS",     "79.116.129.221"),
        "tcpa_consent":      "1",
        "tcpa_consent_date": date.today().isoformat(),
        "email":             _val("email",           "QA_EMAIL",          "qa@pipes.ai"),
        "jornaya_leadid":    _val("jornaya_leadid",  "QA_JORNAYA_LEADID", ""),
        "api_key":           api_key,
        "first_name":        db.get("first_name",    "QA Test"),
        "last_name":         db.get("last_name",     "User"),
        "state":             db.get("state",         "FL"),
        "postal_code":       db.get("postal_code",   "32004"),
    }
    try:
        r = httpx.post(api_url, data=params, timeout=20)
        return jsonify({"ok": True, "http_code": r.status_code, "response": r.text})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
