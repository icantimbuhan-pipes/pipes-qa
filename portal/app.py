import os

from flask import Flask, abort, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user
from jinja2 import ChoiceLoader, FileSystemLoader

from portal.auth.db import get_user_by_id, get_user_permissions, init_auth
from portal.auth.models import User
from portal.auth.routes import bp as auth_bp
from portal.admin.routes import bp as admin_bp
from portal.db import init_db, init_custom_checklists, init_provider_configs, init_dnc_log, init_qa_test_runs, list_sessions
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
from portal.qa_test.routes import bp as qa_test_bp

# URL-prefix → page_key map for permission checks.
# Listed most-specific first so /admin matches before any hypothetical /adm* overlap.
URL_PERMISSION_MAP = [
    ("/admin",        "admin"),
    ("/qa-test",      "qa_test"),
    ("/validator",    "validator"),
    ("/maintenance",  "maintenance"),
    ("/quick-report", "quick_report"),
    ("/checklists",   "checklists"),
    ("/api-configs",  "api_configs"),
    ("/signalmash",   "sms"),
    ("/telgorithm",   "sms"),
    ("/commio",       "sms"),
    ("/upload",       "sms"),
    ("/dnc",          "dnc"),
    ("/daily-qa",     "daily_qa"),
]

# Paths that bypass auth entirely (webhooks, static assets)
AUTH_BYPASS_PREFIXES = ("/static/", "/auth/", "/slack/")


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

    # ── Flask-Login ────────────────────────────────────────────────────────────
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = ""

    @login_manager.user_loader
    def load_user(user_id: str):
        row = get_user_by_id(int(user_id))
        if not row:
            return None
        perms = get_user_permissions(row["role_id"])
        return User(row, perms)

    # ── DB init ────────────────────────────────────────────────────────────────
    init_db()
    init_custom_checklists()
    init_provider_configs()
    init_dnc_log()
    init_qa_test_runs()
    init_auth()
    tel_init()
    sig_init()
    commio_init()

    # ── Blueprints ─────────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp,         url_prefix="/auth")
    app.register_blueprint(admin_bp,        url_prefix="/admin")
    app.register_blueprint(daily_qa_bp,     url_prefix="/daily-qa")
    app.register_blueprint(checklists_bp,   url_prefix="/checklists")
    app.register_blueprint(api_configs_bp,  url_prefix="/api-configs")
    app.register_blueprint(quick_report_bp, url_prefix="/quick-report")
    app.register_blueprint(maintenance_bp,  url_prefix="/maintenance")
    app.register_blueprint(validator_bp,    url_prefix="/validator")
    app.register_blueprint(telgorithm_bp,   url_prefix="/telgorithm")
    app.register_blueprint(signalmash_bp,   url_prefix="/signalmash")
    app.register_blueprint(commio_bp,       url_prefix="/commio")
    app.register_blueprint(slack_dnc_bp)
    app.register_blueprint(dnc_bp)
    app.register_blueprint(qa_test_bp,      url_prefix="/qa-test")

    # ── Auth guard ─────────────────────────────────────────────────────────────
    @app.before_request
    def check_auth():
        path = request.path
        # Skip auth for static files, auth routes, and Slack webhooks
        for prefix in AUTH_BYPASS_PREFIXES:
            if path.startswith(prefix):
                return None

        # Require login for everything else
        if not current_user.is_authenticated:
            if request.method == "GET":
                return redirect(url_for("auth.login", next=path))
            return redirect(url_for("auth.login"))

        # Check page-level permission by URL prefix
        for prefix, page_key in URL_PERMISSION_MAP:
            if path.startswith(prefix):
                if not current_user.can(page_key):
                    abort(403)
                return None

    # ── Error handlers ─────────────────────────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    # ── Main routes ────────────────────────────────────────────────────────────
    @app.route("/")
    def dashboard():
        show_recent = current_user.is_authenticated and current_user.can("quick_report")
        recent = list_sessions(5) if show_recent else []
        return render_template("dashboard.html", recent=recent, show_recent=show_recent)

    @app.route("/upload")
    def upload():
        from datetime import date
        return render_template("upload.html", today=date.today().isoformat())

    @app.route("/sms")
    def sms():
        return redirect(url_for("upload"))

    return app
