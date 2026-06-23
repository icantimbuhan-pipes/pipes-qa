import os

from jinja2 import ChoiceLoader, FileSystemLoader
from flask import Flask, redirect, render_template, url_for

from portal.db import init_db, init_custom_checklists, init_provider_configs, init_dnc_log, list_sessions
from portal.daily_qa.routes import bp as daily_qa_bp
from portal.checklist_builder.routes import bp as checklists_bp
from portal.api_configs.routes import bp as api_configs_bp
from portal.quick_report.routes import bp as quick_report_bp
from portal.maintenance.routes import bp as maintenance_bp
from portal.validator.routes import bp as validator_bp
from sms_deliverability.telgorithm.db import init_db as tel_init
from sms_deliverability.telgorithm.routes import bp as telgorithm_bp
from sms_deliverability.signalmash.db import init_db as sig_init
from sms_deliverability.signalmash.routes import bp as signalmash_bp
from sms_deliverability.commio.db import init_db as commio_init
from sms_deliverability.commio.routes import bp as commio_bp
from portal.slack_dnc.routes import bp as slack_dnc_bp
from portal.dnc.routes import bp as dnc_bp


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
    init_custom_checklists()
    init_provider_configs()
    init_dnc_log()
    tel_init()
    sig_init()
    commio_init()

    app.register_blueprint(daily_qa_bp,   url_prefix="/daily-qa")
    app.register_blueprint(checklists_bp, url_prefix="/checklists")
    app.register_blueprint(api_configs_bp,   url_prefix="/api-configs")
    app.register_blueprint(quick_report_bp, url_prefix="/quick-report")
    app.register_blueprint(maintenance_bp,  url_prefix="/maintenance")
    app.register_blueprint(validator_bp,  url_prefix="/validator")
    app.register_blueprint(telgorithm_bp, url_prefix="/telgorithm")
    app.register_blueprint(signalmash_bp, url_prefix="/signalmash")
    app.register_blueprint(commio_bp,      url_prefix="/commio")
    app.register_blueprint(slack_dnc_bp)
    app.register_blueprint(dnc_bp)

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
