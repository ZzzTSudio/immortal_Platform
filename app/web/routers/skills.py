"""Skill / colleague management routes."""

from __future__ import annotations

import json
import random
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse

from app.database import add_user_skill, get_db_path, get_user_skills, remove_user_skill
from app.paths import builtin_skill_dir, sticker_pack_dir, project_root
from app.settings import DEFAULT_API_BASE, DEFAULT_MODEL
from app.skill_loader import (
    discover_colleagues,
    load_meta,
    resolve_colleague_icon,
    save_skill_display_name,
    colleague_id_for_dir,
)
from app.web.schemas import ImportSkillRequest, RenameSkillRequest

router = APIRouter()


def _get_user_id(request: Request) -> int:
    """Get user_id from cookie, raise 401 if not logged in."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return int(user_id)


def _get_skill_lib_path() -> Path:
    """Get the skill_lib directory path."""
    return project_root() / "skill_lib"


def _get_current_user(request: Request) -> dict:
    user_id = _get_user_id(request)
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, is_admin FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="用户不存在")
    return {
        "id": int(row["id"]),
        "email": row["email"],
        "is_admin": bool(row["is_admin"]),
    }


def _has_chat_content(skill_dir: Path) -> bool:
    return any((skill_dir / name).is_file() for name in ("SKILL.md", "persona_skill.md", "work_skill.md"))


def _build_profile_summary(meta: dict) -> str:
    profile = meta.get("profile")
    if not isinstance(profile, dict):
        return ""

    parts: list[str] = []
    for key in ("company", "role"):
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " · ".join(parts)


def _is_builtin_skill_dir(skill_dir: Path, meta: dict) -> bool:
    builtin = builtin_skill_dir()
    builtin_meta = load_meta(builtin)
    builtin_slug = colleague_id_for_dir(builtin)
    skill_slug = colleague_id_for_dir(skill_dir)
    try:
        if skill_dir.resolve() == builtin.resolve():
            return True
    except OSError:
        pass
    return skill_slug == builtin_slug or skill_dir.name == builtin.name or meta.get("name") == builtin_meta.get("name")


def _iter_platform_skills(request: Request) -> list[dict]:
    user = _get_current_user(request)
    is_admin = user["is_admin"]
    imported_skill_ids = set(get_user_skills(user["id"]))
    skills: list[dict] = []

    root_path = _get_skill_lib_path()
    if not root_path.is_dir():
        return skills

    for skill_dir in sorted((p for p in root_path.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        meta_path = skill_dir / "meta.json"
        if not meta_path.is_file():
            continue

        meta = load_meta(skill_dir)
        if not meta or _is_builtin_skill_dir(skill_dir, meta) or not _has_chat_content(skill_dir):
            continue

        visibility = meta.get("visibility")
        if visibility not in ("public", "private"):
            visibility = "private"
        if not is_admin and visibility != "public":
            continue

        colleague_id = colleague_id_for_dir(skill_dir)
        display_name = meta.get("name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = skill_dir.name

        skills.append({
            "colleague_id": colleague_id,
            "display_name": display_name.strip(),
            "skill_path": str(skill_dir.resolve()),
            "meta": meta,
            "visibility": visibility,
            "intro_summary": _build_profile_summary(meta),
            "avatar_url": f"/api/skills/{colleague_id}/icon",
            "imported": colleague_id in imported_skill_ids,
        })

    return skills


@router.get("/skills")
async def list_skills(request: Request):
    skill_lib_path = _get_skill_lib_path()
    builtin = builtin_skill_dir()
    all_c = discover_colleagues(str(skill_lib_path), builtin)

    # Get user_id from cookie
    user_id = request.cookies.get("user_id")

    # If user is logged in, filter by user's skills
    if user_id:
        user_skill_ids = get_user_skills(int(user_id))
        # Include builtin skills + user's added skills
        colleagues = [
            c for c in all_c
            if c.is_builtin or c.colleague_id in user_skill_ids
        ]
    else:
        # Not logged in, show all (for backward compatibility)
        colleagues = all_c

    return {
        "colleagues": [
            {
                "colleague_id": c.colleague_id,
                "display_name": c.display_name,
                "is_builtin": c.is_builtin,
                "skill_path": str(c.skill_path),
                "meta": load_meta(c.skill_path),
            }
            for c in colleagues
        ]
    }


@router.get("/skills/platform")
async def list_platform_skills(request: Request):
    return {"skills": _iter_platform_skills(request)}


@router.post("/skills/platform/{colleague_id}/import")
async def import_platform_skill(colleague_id: str, request: Request):
    user = _get_current_user(request)
    skill = next((item for item in _iter_platform_skills(request) if item["colleague_id"] == colleague_id), None)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    add_user_skill(user["id"], colleague_id)
    return {"success": True, "colleague_id": colleague_id, "imported": True}


@router.get("/skills/{colleague_id}/icon")
async def get_skill_icon(colleague_id: str, request: Request):
    skill_lib_path = _get_skill_lib_path()
    builtin = builtin_skill_dir()
    all_c = discover_colleagues(str(skill_lib_path), builtin)
    c = next((x for x in all_c if x.colleague_id == colleague_id), None)
    if not c:
        raise HTTPException(status_code=404, detail="Skill not found")
    icon_path = resolve_colleague_icon(c.skill_path)
    if not icon_path.is_file():
        raise HTTPException(status_code=404, detail="Icon not found")
    return FileResponse(str(icon_path))


@router.get("/skills/{colleague_id}/intro")
async def get_skill_intro(colleague_id: str, request: Request):
    skill_lib_path = _get_skill_lib_path()
    builtin = builtin_skill_dir()
    all_c = discover_colleagues(str(skill_lib_path), builtin)
    c = next((x for x in all_c if x.colleague_id == colleague_id), None)
    if not c:
        raise HTTPException(status_code=404, detail="Skill not found")
    intro_path = c.skill_path / "intro.md"
    if not intro_path.is_file():
        return {"content": ""}
    try:
        content = intro_path.read_text(encoding="utf-8", errors="replace")
        return {"content": content}
    except Exception:
        return {"content": ""}


@router.post("/skills/import")
async def import_skill(body: ImportSkillRequest, request: Request):
    _get_user_id(request)  # Verify user is logged in
    root_path = _get_skill_lib_path()
    if not root_path.is_dir():
        root_path.mkdir(parents=True, exist_ok=True)

    src = Path(body.source_dir).resolve()
    skill_file = src / "SKILL.md"
    if not skill_file.is_file():
        raise HTTPException(status_code=400, detail="所选目录下未找到 SKILL.md。")

    dest = root_path / src.name
    if src.resolve() == dest.resolve():
        save_skill_display_name(src, body.display_name)
        return {"success": True, "colleague_id": colleague_id_for_dir(src)}

    if dest.exists():
        if dest.is_dir():
            shutil.rmtree(dest)
    try:
        shutil.copytree(src, dest)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"复制失败：{e}")

    save_skill_display_name(dest, body.display_name)
    return {"success": True, "colleague_id": colleague_id_for_dir(dest)}


@router.post("/skills/upload")
async def upload_skill(request: Request, file: UploadFile = File(...)):
    """Upload a skill folder as a zip file."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    root_path = _get_skill_lib_path()
    if not root_path.is_dir():
        root_path.mkdir(parents=True, exist_ok=True)

    # Create temp directory for extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / "upload.zip"

        # Save uploaded file
        with open(zip_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Extract zip
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_path)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="无效的ZIP文件")

        # Find the skill folder (should contain SKILL.md)
        skill_folder = None
        for item in temp_path.iterdir():
            if item.is_dir() and (item / "SKILL.md").is_file():
                skill_folder = item
                break

        if not skill_folder:
            raise HTTPException(status_code=400, detail="ZIP文件中未找到包含SKILL.md的文件夹")

        # Validate SKILL.md is not empty
        skill_md = skill_folder / "SKILL.md"
        if skill_md.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="SKILL.md文件为空")

        # Copy to skill_lib with duplicate name handling
        base_name = skill_folder.name
        dest = root_path / base_name
        counter = 1

        # If destination exists, append -1, -2, -3, etc.
        while dest.exists():
            dest = root_path / f"{base_name}-{counter}"
            counter += 1

        try:
            shutil.copytree(skill_folder, dest)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"复制失败：{e}")

        # If directory name was changed, update slug in meta.json to match
        if dest.name != base_name:
            meta = load_meta(dest)
            meta["slug"] = dest.name
            meta_path = dest / "meta.json"
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # Get colleague_id and add to user's skills
        colleague_id = colleague_id_for_dir(dest)
        add_user_skill(int(user_id), colleague_id)

        return {"success": True, "colleague_id": colleague_id}


@router.post("/skills/{colleague_id}/rename")
async def rename_skill(colleague_id: str, body: RenameSkillRequest, request: Request):
    _get_user_id(request)  # Verify user is logged in
    skill_lib_path = _get_skill_lib_path()
    builtin = builtin_skill_dir()
    all_c = discover_colleagues(str(skill_lib_path), builtin)
    c = next((x for x in all_c if x.colleague_id == colleague_id), None)
    if not c:
        raise HTTPException(status_code=404, detail="Skill not found")
    if c.is_builtin:
        raise HTTPException(status_code=403, detail="内置同事不可改名")
    save_skill_display_name(c.skill_path, body.name)
    return {"success": True}


@router.delete("/skills/{colleague_id}")
async def delete_skill(colleague_id: str, request: Request):
    user_id = _get_user_id(request)
    skill_lib_path = _get_skill_lib_path()
    builtin = builtin_skill_dir()
    all_c = discover_colleagues(str(skill_lib_path), builtin)
    c = next((x for x in all_c if x.colleague_id == colleague_id), None)
    if not c:
        raise HTTPException(status_code=404, detail="Skill not found")
    if c.is_builtin:
        raise HTTPException(status_code=403, detail="内置同事不可移除")

    # Platform skills are shared repository entries; removing only detaches them from this user.
    remove_user_skill(user_id, colleague_id)

    return {"success": True}


@router.get("/stickers/random")
async def random_sticker():
    d = sticker_pack_dir()
    if not d.is_dir():
        return {"url": None}
    files = []
    for pat in ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.PNG", "*.JPG", "*.JPEG"):
        files.extend(p for p in d.glob(pat) if p.is_file())
    if not files:
        return {"url": None}
    chosen = random.choice(files)
    # Return relative URL that the frontend can use via /static/stickers/
    rel = chosen.name
    return {"url": f"/static/stickers/{rel}"}


