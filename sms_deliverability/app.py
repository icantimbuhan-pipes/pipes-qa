from datetime import date

from flask import Flask, redirect, render_template, url_for

from sms_deliverability.telgorithm.db import init_db as tel_init
from sms_deliverability.telgorithm.routes import bp as telgorithm_bp
from sms_deliverability.signalmash.db import init_db as sig_init
from sms_deliverability.signalmash.routes import bp as signalmash_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "sms-deliverability-dev"
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

    tel_init()
    sig_init()

    app.register_blueprint(telgorithm_bp,  url_prefix="/telgorithm")
    app.register_blueprint(signalmash_bp,  url_prefix="/signalmash")

    @app.route("/")
    def index():
        return redirect(url_for("upload"))

    @app.route("/upload")
    def upload():
        return render_template("upload.html", today=date.today().isoformat())

    return app
