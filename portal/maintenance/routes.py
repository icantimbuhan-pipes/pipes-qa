import importlib
from pathlib import Path

from dotenv import dotenv_values, set_key, unset_key
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from portal.maintenance.schemas import PROVIDER_SCHEMAS, SHARED_PARAMS

bp = Blueprint("maintenance", __name__, template_folder="templates")

ENV_PATH = Path(".env")


def _env_values() -> dict:
    if ENV_PATH.exists():
        return dict(dotenv_values(ENV_PATH))
    return {}


def _provider_status(schema: dict, env: dict) -> str:
    required = [p["env"] for p in schema["params"] if p.get("required")]
    if not required:
        return "active"
    filled = [e for e in required if env.get(e, "").strip()]
    if len(filled) == len(required):
        return "active"
    if filled:
        return "partial"
    return "unconfigured"


@bp.route("/")
def index():
    env = _env_values()
    providers = [
        {**s, "status": _provider_status(s, env)}
        for s in PROVIDER_SCHEMAS
    ]
    return render_template(
        "maintenance/index.html",
        shared_params=SHARED_PARAMS,
        providers=providers,
        env=env,
    )


@bp.route("/global", methods=["POST"])
def save_global():
    ENV_PATH.touch()
    for p in SHARED_PARAMS:
        val = request.form.get(p["env"], "").strip()
        if val:
            set_key(str(ENV_PATH), p["env"], val)
    flash("Global settings saved.", "success")
    return redirect(url_for("maintenance.index"))


@bp.route("/provider/<key>", methods=["POST"])
def save_provider(key: str):
    schema = next((s for s in PROVIDER_SCHEMAS if s["key"] == key), None)
    if not schema:
        flash("Provider not found.", "error")
        return redirect(url_for("maintenance.index"))
    ENV_PATH.touch()
    for p in schema["params"]:
        val = request.form.get(p["env"], "").strip()
        if val:
            set_key(str(ENV_PATH), p["env"], val)
    flash(f"{schema['name']} saved.", "success")
    return redirect(url_for("maintenance.index") + f"#provider-{key}")


@bp.route("/provider/<key>/clear/<env_var>", methods=["POST"])
def clear_env(key: str, env_var: str):
    if ENV_PATH.exists():
        unset_key(str(ENV_PATH), env_var)
    flash(f"{env_var} cleared.", "success")
    return redirect(url_for("maintenance.index") + f"#provider-{key}")


@bp.route("/provider/<key>/test", methods=["POST"])
def test_provider(key: str):
    schema = next((s for s in PROVIDER_SCHEMAS if s["key"] == key), None)
    if not schema:
        return jsonify({"ok": False, "error": "Provider not found"}), 404
    try:
        mod = importlib.import_module(schema["module"])
        result = mod.trigger()
        return jsonify({"ok": True, "result": result})
    except NotImplementedError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
