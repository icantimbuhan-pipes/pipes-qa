from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, row, permissions: set[str]):
        self.id = str(row["id"])
        self.email = row["email"]
        self.username = row["username"]
        self.role_id = row["role_id"]
        self.role_name = (row["role_name"] or "") if row["role_name"] is not None else ""
        self._is_active = bool(row["is_active"])
        self._permissions = permissions

    @property
    def is_active(self) -> bool:
        return self._is_active

    def can(self, page_key: str) -> bool:
        if self.role_name == "Admin":
            return True
        return page_key in self._permissions

    def get_initials(self) -> str:
        parts = self.username.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.username[:2].upper() if len(self.username) >= 2 else self.username.upper()
