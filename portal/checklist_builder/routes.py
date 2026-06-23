import json
import re
import uuid
from types import SimpleNamespace

from flask import Blueprint, flash, redirect, render_template, request, url_for

from portal.db import (
    delete_custom_checklist, get_custom_checklist,
    list_custom_checklists, list_provider_configs, save_custom_checklist,
)
from runner.interactive import CHECKLISTS

bp = Blueprint("checklists", __name__, template_folder="templates")

_BASE_PROVIDER_OPTIONS = [
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
_BASE_KEYS = {p["key"] for p in _BASE_PROVIDER_OPTIONS}


def _get_provider_options() -> list:
    """Built-in providers + any custom ones saved in API Configs."""
    options = list(_BASE_PROVIDER_OPTIONS)
    for row in list_provider_configs():
        row = dict(row)
        if row["key"] not in _BASE_KEYS:
            options.append({"key": row["key"], "name": row["name"] + " ✦"})
    return options


# Keep PROVIDER_OPTIONS as a property for backwards compat in templates
PROVIDER_OPTIONS = _BASE_PROVIDER_OPTIONS


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def json_to_checklist(sections_json: str) -> list:
    """Convert stored JSON sections back into SimpleNamespace objects for the wizard."""
    sections_data = json.loads(sections_json or "[]")
    result = []
    for sec in sections_data:
        items_ns = []
        for item in sec.get("items", []):
            sub_calls = [
                SimpleNamespace(
                    instruction=s.get("instruction", ""),
                    note=s.get("note", ""),
                )
                for s in item.get("sub_calls", [])
            ]
            items_ns.append(SimpleNamespace(
                id=item.get("id", ""),
                text=item.get("text", ""),
                note=item.get("note", ""),
                bullets=item.get("bullets", []),
                trigger_call=item.get("trigger_call", False),
                call_instruction=item.get("call_instruction", ""),
                sub_calls=sub_calls,
                provider_key=item.get("provider_key", ""),
            ))
        result.append(SimpleNamespace(
            id=sec.get("id", ""),
            title=sec.get("title", ""),
            trigger_call_at_start=sec.get("trigger_call_at_start", False),
            start_instruction=sec.get("start_instruction", ""),
            provider_key=sec.get("provider_key", ""),
            items=items_ns,
        ))
    return result


@bp.route("/")
def index():
    custom = list_custom_checklists()
    return render_template(
        "checklist_builder/list.html",
        hardcoded=CHECKLISTS,
        custom=custom,
        providers={p["key"]: p["name"] for p in _get_provider_options()},
    )


@bp.route("/new")
def new():
    return render_template(
        "checklist_builder/edit.html",
        checklist=None,
        providers=_get_provider_options(),
        sections_json="[]",
    )


@bp.route("/save", methods=["POST"])
@bp.route("/<checklist_id>/save", methods=["POST"])
def save(checklist_id: str = None):
    name             = request.form.get("name", "").strip()
    report_type      = request.form.get("report_type", "daily")
    default_provider = request.form.get("default_provider", "heavy_khomp")
    sections_json    = request.form.get("sections_json", "[]")

    if not name:
        flash("Checklist name is required.", "error")
        return redirect(request.referrer or url_for("checklists.new"))

    # Validate JSON
    try:
        json.loads(sections_json)
    except Exception:
        flash("Invalid sections data.", "error")
        return redirect(request.referrer or url_for("checklists.new"))

    cid = checklist_id or str(uuid.uuid4())
    key = _slug(name)

    save_custom_checklist(
        id=cid,
        key=key,
        name=name,
        report_type=report_type,
        default_provider=default_provider,
        sections_json=sections_json,
    )
    flash(f'Checklist "{name}" saved.', "success")
    return redirect(url_for("checklists.edit", checklist_id=cid))


@bp.route("/<checklist_id>/edit")
def edit(checklist_id: str):
    cl = get_custom_checklist(checklist_id)
    if not cl:
        flash("Checklist not found.", "error")
        return redirect(url_for("checklists.index"))
    return render_template(
        "checklist_builder/edit.html",
        checklist=dict(cl),
        providers=_get_provider_options(),
        sections_json=cl["sections_json"] or "[]",
    )


@bp.route("/<checklist_id>/delete", methods=["POST"])
def delete(checklist_id: str):
    cl = get_custom_checklist(checklist_id)
    if cl:
        delete_custom_checklist(checklist_id)
        flash(f'Checklist "{cl["name"]}" deleted.', "success")
    return redirect(url_for("checklists.index"))
