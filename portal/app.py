import os

from jinja2 import ChoiceLoader, FileSystemLoader
from flask import Flask, redirect, render_template, url_for

from portal.db import init_db, list_sessions
from portal.daily_qa.routes import bp as daily_qa_bp
from sms_deliverability.telgorithm.db import init_db as tel_init
from sms_deliverability.telgorithm.routes import bp as telgorithm_bp
from sms_deliverability.signalmash.db import init_db as sig_init
from sms_deliverability.signalmash.routes import bp as signalmash_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "pipes-qa-portal-dev"
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

    # Merge portal + sms_deliverability template folders
    portal_tmpl = os.path.join(os.path.dirname(__file__), "templates")
    sms_tmpl = os.path.join(os.path.dirname(__file__), "..", "sms_deliverability", "templates")
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(portal_tmpl),
        FileSystemLoader(os.path.abspath(sms_tmpl)),
    ])

    init_db()
    tel_init()
    sig_init()

    app.register_blueprint(daily_qa_bp,   url_prefix="/daily-qa")
    app.register_blueprint(telgorithm_bp, url_prefix="/telgorithm")
    app.register_blueprint(signalmash_bp, url_prefix="/signalmash")

    @app.route("/")
    def dashboard():
        recent = list_sessions(5)
        return render_template("dashboard.html", recent=recent)

    @app.route("/upload")
    def upload():
        from datetime import date
        return render_template("upload.html", today=date.today().isoformat())

    @app.route("/sms")
    def sms():
        return redirect(url_for("upload"))

    return app
