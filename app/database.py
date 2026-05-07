"""User database management using SQLite."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Optional

from app.paths import project_root


def get_db_path() -> Path:
    """Return the path to the user database."""
    return project_root() / "users.db"


def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """Initialize the database with required tables."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            avatar TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # User skills table (many-to-many relationship)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            colleague_id TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, colleague_id)
        )
    """)

    # User settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            avatar TEXT,
            font_size INTEGER DEFAULT 16,
            api_base TEXT,
            api_key TEXT,
            model TEXT,
            skill_root_path TEXT,
            web_search_url TEXT,
            web_search_api_key TEXT,
            web_search_enabled INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Create default admin user if not exists
    cursor.execute("SELECT id FROM users WHERE email = ?", ("admin@fanvil.com",))
    if not cursor.fetchone():
        admin_hash = hash_password("admin2025")
        cursor.execute(
            "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, 1)",
            ("admin@fanvil.com", admin_hash)
        )

    conn.commit()
    conn.close()


def create_user(email: str, password: str, avatar: str = "") -> Optional[int]:
    """Create a new user. Returns user_id if successful, None if email exists."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        password_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (email, password_hash, avatar) VALUES (?, ?, ?)",
            (email, password_hash, avatar)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def verify_user(email: str, password: str) -> Optional[dict]:
    """Verify user credentials. Returns user dict if valid, None otherwise."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    password_hash = hash_password(password)
    cursor.execute(
        "SELECT id, email, avatar, is_admin FROM users WHERE email = ? AND password_hash = ?",
        (email, password_hash)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "email": row["email"],
            "avatar": row["avatar"] or "",
            "is_admin": bool(row["is_admin"])
        }
    return None


def get_all_users() -> list[dict]:
    """Get all users (admin only)."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, email, avatar, is_admin, created_at FROM users")
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "email": row["email"],
            "avatar": row["avatar"] or "",
            "is_admin": bool(row["is_admin"]),
            "created_at": row["created_at"]
        }
        for row in rows
    ]


def update_user(user_id: int, email: str = None, password: str = None, avatar: str = None) -> bool:
    """Update user information. Returns True if successful."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    updates = []
    params = []

    if email is not None:
        updates.append("email = ?")
        params.append(email)
    if password is not None:
        updates.append("password_hash = ?")
        params.append(hash_password(password))
    if avatar is not None:
        updates.append("avatar = ?")
        params.append(avatar)

    if not updates:
        conn.close()
        return False

    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"

    try:
        cursor.execute(query, params)
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except sqlite3.IntegrityError:
        conn.close()
        return False


def delete_user(user_id: int) -> bool:
    """Delete a user. Returns True if successful."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def add_user_skill(user_id: int, colleague_id: str) -> bool:
    """Add a skill to user's list. Returns True if successful."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO user_skills (user_id, colleague_id) VALUES (?, ?)",
            (user_id, colleague_id)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def remove_user_skill(user_id: int, colleague_id: str) -> bool:
    """Remove a skill from user's list. Returns True if successful."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM user_skills WHERE user_id = ? AND colleague_id = ?",
        (user_id, colleague_id)
    )
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def get_user_skills(user_id: int) -> list[str]:
    """Get list of colleague_ids for a user."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        "SELECT colleague_id FROM user_skills WHERE user_id = ? ORDER BY added_at",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [row[0] for row in rows]


def get_user_settings(user_id: int) -> Optional[dict]:
    """Get user settings."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def save_user_settings(user_id: int, settings: dict) -> bool:
    """Save user settings."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM user_settings WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    
    if exists:
        updates = []
        params = []
        for key, value in settings.items():
            if key not in ('user_id', 'id'):
                updates.append(f"{key} = ?")
                params.append(value)
        if updates:
            params.append(user_id)
            query = f"UPDATE user_settings SET {', '.join(updates)} WHERE user_id = ?"
            cursor.execute(query, params)
    else:
        settings['user_id'] = user_id
        columns = ', '.join(settings.keys())
        placeholders = ', '.join(['?' for _ in settings])
        query = f"INSERT INTO user_settings ({columns}) VALUES ({placeholders})"
        cursor.execute(query, list(settings.values()))
    
    conn.commit()
    conn.close()
    return True
