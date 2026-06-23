import logging
from flask import Blueprint, render_template, request, jsonify

from portal.db import log_dnc, list_dnc_log
from portal.slack_dnc.routes import dnc_number, extract_phones

log = logging.getLogger("dnc")
bp  = Blueprint("dnc", __name__, template_folder="templates")


@bp.route("/dnc")
def index():
    history = list_dnc_log(100)
    return render_template("dnc/index.html", history=history)


@bp.route("/dnc/submit", methods=["POST"])
def submit():
    """Parse text input, DNC every number found, return JSON results."""
    text = request.form.get("numbers", "").strip()
    if not text:
        return jsonify({"error": "No input provided"}), 400

    phones = extract_phones(text)
    if not phones:
        return jsonify({"error": "No valid US phone numbers found", "parsed": []}), 422

    results = []
    for phone in phones:
        ok = dnc_number(phone)
        log_dnc(phone, "success" if ok else "failed", source="manual")
        results.append({
            "phone": phone,
            "formatted": f"({phone[:3]}) {phone[3:6]}-{phone[6:]}",
            "status": "success" if ok else "failed",
        })

    return jsonify({"results": results})


@bp.route("/dnc/parse", methods=["POST"])
def parse():
    """Preview: return parsed numbers without DNCing."""
    text = request.form.get("numbers", "").strip()
    phones = extract_phones(text) if text else []
    return jsonify({
        "phones": [
            {"raw": p, "formatted": f"({p[:3]}) {p[3:6]}-{p[6:]}"}
            for p in phones
        ]
    })
