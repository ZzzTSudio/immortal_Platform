"""Authentication routes."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.database import (
    create_user,
    delete_user,
    get_all_users,
    get_db_path,
    init_db,
    update_user,
    verify_user,
)

router = APIRouter()

# Initialize database on module load
init_db()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    avatar: Optional[str] = None


def validate_email(email: str) -> bool:
    """Validate email format and domain."""
    if not re.match(r"^[a-zA-Z0-9._%+-]+@fanvil\.com$", email):
        return False
    return True


def validate_password(password: str) -> bool:
    """Validate password: at least 6 chars, contains letters and numbers."""
    if len(password) < 6:
        return False
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_letter and has_digit


@router.post("/auth/register")
async def register(body: RegisterRequest):
    """Register a new user."""
    # Validate email
    if not validate_email(body.email):
        raise HTTPException(
            status_code=400,
            detail="邮箱必须是 @fanvil.com 后缀"
        )

    # Validate password
    if not validate_password(body.password):
        raise HTTPException(
            status_code=400,
            detail="密码至少6位且需要包含英文和数字"
        )

    # Create user
    user_id = create_user(body.email, body.password)
    if user_id is None:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    return {"success": True, "message": "注册成功"}


@router.post("/auth/login")
async def login(body: LoginRequest, response: Response):
    """Login and create session."""
    user = verify_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    # Set session cookie (simple implementation)
    response.set_cookie(
        key="user_id",
        value=str(user["id"]),
        httponly=True,
        max_age=7 * 24 * 3600,  # 7 days
        samesite="lax"
    )

    return {
        "success": True,
        "user": user
    }


@router.post("/auth/logout")
async def logout(response: Response):
    """Logout and clear session."""
    response.delete_cookie("user_id")
    return {"success": True}


@router.get("/auth/me")
async def get_current_user(request: Request):
    """Get current logged-in user."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # For simplicity, we'll fetch user from database
    # In production, you'd want to use proper session management
    from app.database import get_db_path
    import sqlite3

    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, email, avatar, is_admin FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="用户不存在")

    return {
        "id": row["id"],
        "email": row["email"],
        "avatar": row["avatar"] or "",
        "is_admin": bool(row["is_admin"])
    }


def require_admin(request: Request) -> int:
    """Return current user_id when the cookie belongs to an admin."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    import sqlite3

    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return int(user_id)


@router.get("/admin/users")
async def list_users(request: Request):
    """List all users (admin only)."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # Check if admin
    from app.database import get_db_path
    import sqlite3

    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    users = get_all_users()
    return {"users": users}


@router.put("/admin/users/{target_user_id}")
async def update_user_admin(target_user_id: int, body: UpdateUserRequest, request: Request):
    """Update user (admin only)."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # Check if admin
    from app.database import get_db_path
    import sqlite3

    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    # Validate email if provided
    if body.email is not None and not validate_email(body.email):
        raise HTTPException(status_code=400, detail="邮箱必须是 @fanvil.com 后缀")

    # Validate password if provided
    if body.password is not None and not validate_password(body.password):
        raise HTTPException(status_code=400, detail="密码至少6位且需要包含英文和数字")

    success = update_user(target_user_id, body.email, body.password, body.avatar)
    if not success:
        raise HTTPException(status_code=400, detail="更新失败")

    return {"success": True}


@router.delete("/admin/users/{target_user_id}")
async def delete_user_admin(target_user_id: int, request: Request):
    """Delete user (admin only)."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # Check if admin
    from app.database import get_db_path
    import sqlite3

    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    success = delete_user(target_user_id)
    if not success:
        raise HTTPException(status_code=400, detail="删除失败")

    return {"success": True}
