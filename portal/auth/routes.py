from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from portal.auth.db import get_user_row, get_user_permissions, update_last_login
from portal.auth.models import User

bp = Blueprint("auth", __name__, template_folder="templates")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        identifier = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        row = get_user_row(identifier)
        if row and bool(row["is_active"]) and check_password_hash(row["password_hash"], password):
            perms = get_user_permissions(row["role_id"])
            user = User(row, perms)
            login_user(user, remember=True)
            update_last_login(row["id"])
            next_url = request.args.get("next", "")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        error = "Invalid email/username or password, or account is inactive."

    return render_template("auth/login.html", error=error)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
