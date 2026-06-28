# /auth:rbac — Auth & RBAC Reference

Login system, roles, and per-page permissions for the Pipes.QA Portal.

---

## Architecture

| Layer | File | What it does |
|-------|------|-------------|
| DB | `portal/auth/db.py` | Tables + seed + all CRUD |
| Model | `portal/auth/models.py` | `User(UserMixin)` with `.can(page_key)` |
| Auth routes | `portal/auth/routes.py` | `/auth/login`, `/auth/logout` |
| Admin routes | `portal/admin/routes.py` | `/admin/users`, `/admin/permissions` |
| Guard | `portal/app.py` → `check_auth()` | Global before_request — requires login + enforces page permissions |

---

## Default credentials

| Email | Password | Role |
|-------|----------|------|
| `admin@pipes.ai` | `admin123` | Admin |

Change it immediately: **Admin → Users → Edit**.

---

## Roles

| Role | What they can access |
|------|---------------------|
| **Admin** | Everything — bypasses all permission checks |
| **Manager** | All pages except Admin panel |
| **QA** | Dashboard, Daily QA, Hourly QA, Quick Report, Validator, QA Testing |
| **Viewer** | Dashboard, Daily QA (read only) |

---

## Page keys

| Key | URL prefix | Default roles |
|-----|-----------|--------------|
| `dashboard` | `/` | All |
| `daily_qa` | `/daily-qa` | Manager, QA, Viewer |
| `hourly_qa` | `/daily-qa` | Manager, QA |
| `quick_report` | `/quick-report` | Manager, QA |
| `checklists` | `/checklists` | Manager |
| `api_configs` | `/api-configs` | Manager |
| `sms` | `/upload`, `/telgorithm`, `/signalmash`, `/commio` | Manager |
| `dnc` | `/dnc` | Manager |
| `validator` | `/validator` | Manager, QA |
| `maintenance` | `/maintenance` | Manager |
| `qa_test` | `/qa-test` | Manager, QA |
| `admin` | `/admin` | Admin only |

---

## How permissions work

1. Every request goes through `check_auth()` in `portal/app.py`
2. Not logged in → redirected to `/auth/login`
3. Logged in, URL matches a prefix → `current_user.can(page_key)` checked
4. Returns 403 if denied → renders `portal/templates/403.html`
5. Admin role → `can()` always returns True (bypasses all checks)

---

## Adding a new protected page

1. Register the URL prefix in `URL_PERMISSION_MAP` in `portal/app.py`:
   ```python
   ("/my-new-page", "my_page"),
   ```
2. Add the page to `SEED_PAGES` in `portal/auth/db.py`:
   ```python
   ("my_page", "My Page", "/my-new-page", "🆕", 12),
   ```
3. Add it to `DEFAULT_PERMISSIONS` for appropriate roles.
4. Add the nav item to `portal/templates/base.html` with the permission check:
   ```html
   {% if current_user.can('my_page') %}
   <a class="nav-item" href="/my-new-page">🆕 My Page</a>
   {% endif %}
   ```
5. **Note:** Existing `portal_qa.db` won't auto-add the new page on restart.
   Delete the DB to re-seed, or insert manually:
   ```sql
   INSERT OR IGNORE INTO pages(key,name,url_prefix,icon,sort_order) VALUES('my_page','My Page','/my-new-page','🆕',12);
   ```

---

## Admin portal

| URL | What it does |
|-----|-------------|
| `/admin/users` | List all users |
| `/admin/users/new` | Create user |
| `/admin/users/<id>/edit` | Edit user / reset password |
| `/admin/users/<id>/delete` | Delete user (POST) |
| `/admin/permissions` | Role permission matrix |
| `/admin/permissions?role_id=N` | Permissions for a specific role |

---

## Database tables

```sql
users            (id, email, username, password_hash, role_id, is_active, created_at, last_login)
roles            (id, name, description, is_system, created_at)
pages            (id, key, name, url_prefix, icon, sort_order)
role_permissions (role_id, page_id, can_view, can_edit, can_delete, is_admin)
```

All in `data/portal_qa.db` alongside the other portal tables.

---

## Future enhancements (planned)

- Two-factor authentication
- Audit logs (who accessed what, when)
- Feature flags (per-user feature toggles)
- Activity history
- Password expiration policies
- SSO integration
