from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from portal.auth.db import (
    create_role, create_user, delete_role, delete_user, get_all_permissions,
    get_role, get_user_by_id, list_pages, list_roles, list_users,
    save_permissions, update_user,
)

bp = Blueprint("admin_panel", __name__, template_folder="templates")


def _require_admin():
    if not current_user.is_authenticated or not current_user.can("admin"):
        abort(403)


# ── Users ─────────────────────────────────────────────────────────────────────

@bp.route("/")
@login_required
def index():
    _require_admin()
    return redirect(url_for("admin_panel.users"))


@bp.route("/users")
@login_required
def users():
    _require_admin()
    return render_template("admin/users.html",
                           users=list_users(),
                           roles=list_roles())


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
def user_new():
    _require_admin()
    roles = list_roles()
    error = None

    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role_id  = request.form.get("role_id", type=int)
        is_active = request.form.get("is_active") == "1"

        if not email or not username or not password or not role_id:
            error = "All fields are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            try:
                create_user(email, username, password, role_id, is_active)
                flash(f"User '{username}' created.", "success")
                return redirect(url_for("admin_panel.users"))
            except Exception as exc:
                error = f"Could not create user: {exc}"

    return render_template("admin/user_form.html",
                           roles=roles, user=None, error=error, action="Create")


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def user_edit(user_id: int):
    _require_admin()
    row = get_user_by_id(user_id)
    if not row:
        abort(404)
    roles = list_roles()
    error = None

    if request.method == "POST":
        email     = request.form.get("email", "").strip()
        username  = request.form.get("username", "").strip()
        role_id   = request.form.get("role_id", type=int)
        is_active = request.form.get("is_active") == "1"
        password  = request.form.get("password", "").strip() or None

        if not email or not username or not role_id:
            error = "Email, username, and role are required."
        elif password and len(password) < 6:
            error = "New password must be at least 6 characters."
        else:
            try:
                update_user(user_id, email, username, role_id, is_active, password)
                flash(f"User '{username}' updated.", "success")
                return redirect(url_for("admin_panel.users"))
            except Exception as exc:
                error = f"Could not update user: {exc}"

    return render_template("admin/user_form.html",
                           roles=roles, user=row, error=error, action="Edit")


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def user_delete(user_id: int):
    _require_admin()
    if user_id == int(current_user.id):
        flash("You cannot delete your own account.", "error")
    else:
        delete_user(user_id)
        flash("User deleted.", "success")
    return redirect(url_for("admin_panel.users"))


# ── Permissions ───────────────────────────────────────────────────────────────

@bp.route("/permissions", methods=["GET", "POST"])
@login_required
def permissions():
    _require_admin()
    roles = list_roles()
    pages = list_pages()
    all_perms = get_all_permissions()

    selected_role_id = request.args.get("role_id", type=int)
    if selected_role_id is None and roles:
        selected_role_id = roles[0]["id"]

    if request.method == "POST":
        action = request.form.get("action", "save_perms")

        if action == "create_role":
            name = request.form.get("role_name", "").strip()
            desc = request.form.get("role_desc", "").strip()
            if name:
                try:
                    create_role(name, desc)
                    flash(f"Role '{name}' created.", "success")
                except Exception as exc:
                    flash(f"Could not create role: {exc}", "error")
            return redirect(url_for("admin_panel.permissions"))

        if action == "delete_role":
            rid = request.form.get("role_id", type=int)
            if rid:
                role = get_role(rid)
                if role and role["is_system"]:
                    flash("System roles cannot be deleted.", "error")
                else:
                    delete_role(rid)
                    flash("Role deleted.", "success")
            return redirect(url_for("admin_panel.permissions"))

        # save_perms
        role_id = request.form.get("role_id", type=int)
        if role_id:
            role = get_role(role_id)
            if role and role["name"] == "Admin":
                flash("Admin role always has full access — permissions cannot be restricted.", "error")
                return redirect(url_for("admin_panel.permissions", role_id=role_id))
            new_perms: dict = {}
            for page in pages:
                pid = page["id"]
                new_perms[pid] = {
                    "can_view":   bool(request.form.get(f"view_{pid}")),
                    "can_edit":   bool(request.form.get(f"edit_{pid}")),
                    "can_delete": bool(request.form.get(f"del_{pid}")),
                    "is_admin":   bool(request.form.get(f"adm_{pid}")),
                }
            save_permissions(role_id, new_perms)
            flash("Permissions saved.", "success")
            return redirect(url_for("admin_panel.permissions", role_id=role_id))

    return render_template("admin/permissions.html",
                           roles=roles, pages=pages,
                           all_perms=all_perms,
                           selected_role_id=selected_role_id)
