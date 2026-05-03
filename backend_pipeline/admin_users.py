"""Admin-only CRUD for application users (not the static admin account)."""
from __future__ import annotations

import logging
from typing import Any

from auth import hash_password
from database import get_connection

log = logging.getLogger(__name__)

VALID_ROLES = frozenset({"N1", "N2", "N3"})


def list_users() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, role, created_at
                FROM users
                ORDER BY id ASC
                """
            )
            rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            uid, email, role, created_at = r
            ca = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
            out.append({"id": uid, "email": email, "role": role, "created_at": ca})
        return out
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, role, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        uid, email, role, created_at = row
        ca = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
        return {"id": uid, "email": email, "role": role, "created_at": ca}
    finally:
        conn.close()


def create_user(*, email: str, password: str, role: str) -> tuple[bool, str, dict | None]:
    if role not in VALID_ROLES:
        return False, "Role must be N1, N2, or N3", None
    email = (email or "").strip().lower()
    if not email:
        return False, "Email is required", None
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters", None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return False, "Email already registered", None
            ph = hash_password(password)
            cur.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) RETURNING id",
                (email, ph, role),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
        u = get_user_by_id(int(new_id))
        return True, "User created", u
    except Exception as e:
        conn.rollback()
        log.exception("create_user failed: %s", e)
        return False, "Failed to create user", None
    finally:
        conn.close()


def update_user(
    user_id: int,
    *,
    email: str | None = None,
    password: str | None = None,
    role: str | None = None,
) -> tuple[bool, str, dict | None]:
    if email is not None:
        email = email.strip().lower()
        if not email:
            return False, "Email cannot be empty", None
    if role is not None and role not in VALID_ROLES:
        return False, "Role must be N1, N2, or N3", None
    if password is not None and len(password) < 6:
        return False, "Password must be at least 6 characters", None
    if email is None and password is None and role is None:
        return False, "Nothing to update", None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cur.fetchone():
                return False, "User not found", None
            if email is not None:
                cur.execute("SELECT id FROM users WHERE email = %s AND id <> %s", (email, user_id))
                if cur.fetchone():
                    return False, "Email already in use", None
            sets: list[str] = []
            args: list[Any] = []
            if email is not None:
                sets.append("email = %s")
                args.append(email)
            if password is not None:
                sets.append("password_hash = %s")
                args.append(hash_password(password))
            if role is not None:
                sets.append("role = %s")
                args.append(role)
            args.append(user_id)
            cur.execute(
                f"UPDATE users SET {', '.join(sets)} WHERE id = %s",
                tuple(args),
            )
            conn.commit()
        return True, "User updated", get_user_by_id(user_id)
    except Exception as e:
        conn.rollback()
        log.exception("update_user failed: %s", e)
        return False, "Failed to update user", None
    finally:
        conn.close()


def delete_user(user_id: int) -> tuple[bool, str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            if cur.rowcount == 0:
                conn.rollback()
                return False, "User not found"
            conn.commit()
        return True, "User deleted"
    except Exception as e:
        conn.rollback()
        log.exception("delete_user failed: %s", e)
        return False, "Failed to delete user"
    finally:
        conn.close()
