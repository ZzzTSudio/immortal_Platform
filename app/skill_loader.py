"""Load skill folders into a single system prompt string."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.paths import builtin_skill_dir, default_colleague_icon_path

# Approximate limit to avoid huge prompts (character-based MVP).
MAX_SYSTEM_CHARS = 48_000
MAX_KNOWLEDGE_FILE_CHARS = 12_000

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL | re.MULTILINE)


def strip_frontmatter(markdown: str) -> str:
    """Remove leading YAML frontmatter (--- ... ---) if present."""
    s = markdown.lstrip("\ufeff")
    if not s.startswith("---"):
        return s
    m = _FRONTMATTER_RE.match(s)
    if m:
        return s[m.end() :].lstrip()
    return s


def _read_optional(path: Path) -> str | None:
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    return None


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n\n…(已截断)"


def load_meta(skill_dir: Path) -> dict:
    meta_path = skill_dir / "meta.json"
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_skill_display_name(skill_dir: Path, display_name: str) -> None:
    """Write or update ``name`` in ``meta.json`` (creates file if missing)."""
    meta_path = skill_dir / "meta.json"
    meta = load_meta(skill_dir)
    meta["name"] = display_name.strip()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_system_prompt(skill_dir: Path) -> str:
    """Concatenate persona → work → SKILL, then optional knowledge files."""
    parts: list[str] = []

    order = [
        skill_dir / "persona_skill.md",
        skill_dir / "work_skill.md",
        skill_dir / "SKILL.md",
    ]
    for p in order:
        raw = _read_optional(p)
        if raw:
            body = strip_frontmatter(raw).strip()
            if body:
                label = p.stem.upper()
                parts.append(f"## [{label}]\n\n{body}")

    meta = load_meta(skill_dir)
    sources = meta.get("knowledge_sources") or []
    if isinstance(sources, list):
        for rel in sources:
            if not isinstance(rel, str):
                continue
            kpath = (skill_dir / rel).resolve()
            if not str(kpath).startswith(str(skill_dir.resolve())):
                continue
            if kpath.is_file():
                kt = kpath.read_text(encoding="utf-8", errors="replace")
                kt = _truncate(kt, MAX_KNOWLEDGE_FILE_CHARS)
                parts.append(f"## [Knowledge: {rel}]\n\n{kt}")

    combined = "\n\n---\n\n".join(parts)
    if not combined.strip():
        raise ValueError(f"Skill 目录无有效内容: {skill_dir}")

    # 全局回复约束：偏口语、无 Markdown、可少量 emoji（对所有同事生效）
    reply_style = """## [回复风格]

请遵守：
- 像真人聊天：自然、有语气，避免条目式、报告式、总结式腔调。
- 不要使用 Markdown（不要用 # 标题、**粗体**、列表符号、代码围栏等），用纯文本说话。
- 表达情绪请直接插入 Unicode 彩色表情符号（例如 😂、👍、🙏），不要使用方括号包裹的文字如 [捂脸哭]、[笑哭] 等——那些在微信里会显示成贴图，在普通文本里只会显示成方括号汉字。
- 可以小概率在句子里带一个 emoji 点缀情绪，不要堆砌多个。"""

    combined = combined + "\n\n---\n\n" + reply_style
    return _truncate(combined, MAX_SYSTEM_CHARS)


@dataclass(frozen=True)
class ColleagueInfo:
    """A selectable colleague backed by one skill directory."""

    colleague_id: str
    display_name: str
    skill_path: Path
    is_builtin: bool


def _slug_from_dir(skill_dir: Path, meta: dict) -> str:
    s = meta.get("slug")
    if isinstance(s, str) and s.strip():
        return s.strip()
    return skill_dir.name


def colleague_id_for_dir(skill_dir: Path) -> str:
    """Stable colleague id (slug) for a skill directory — matches discover_colleagues."""
    return _slug_from_dir(skill_dir, load_meta(skill_dir))


def _name_from_meta(skill_dir: Path, meta: dict) -> str:
    n = meta.get("name")
    if isinstance(n, str) and n.strip():
        return n.strip()
    return skill_dir.name


def _first_skill_icon_file(icon_dir: Path) -> Path | None:
    if not icon_dir.is_dir():
        return None
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"):
        for p in sorted(icon_dir.glob(pattern)):
            if p.is_file():
                return p.resolve()
    return None


def resolve_colleague_icon(skill_dir: Path) -> Path:
    """
    Use ``avatar.png`` first, then the first image in ``skill_dir/icon/`` (png/jpg/jpeg),
    else bundled default icon.

    For the builtin colleague: if the user's ``skill_root/<same-skill>`` has no ``icon/`` but
    the packaged builtin does, use the builtin avatar (scanned entry overrides builtin path but
    should still show the packaged photo).
    """
    avatar = skill_dir / "avatar.png"
    if avatar.is_file():
        return avatar.resolve()
    p = _first_skill_icon_file(skill_dir / "icon")
    if p is not None:
        return p
    builtin = builtin_skill_dir()
    builtin_meta = load_meta(builtin)
    skill_meta = load_meta(skill_dir)
    builtin_slug = _slug_from_dir(builtin, builtin_meta)
    skill_slug = _slug_from_dir(skill_dir, skill_meta)
    try:
        if (
            skill_dir.resolve() != builtin.resolve()
            and (skill_slug == builtin_slug or skill_dir.name == builtin.name)
        ):
            p2 = _first_skill_icon_file(builtin / "icon")
            if p2 is not None:
                return p2
    except OSError:
        pass
    return default_colleague_icon_path()


def iter_skill_dirs(root: Path) -> Iterator[Path]:
    if not root.is_dir():
        return
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            yield child


def discover_colleagues(skill_root: str | None, builtin_skill: Path) -> list[ColleagueInfo]:
    """
    Merge the builtin colleague with subfolders under ``skill_root`` that contain ``SKILL.md``.
    If ``skill_root`` contains a skill with the same slug or directory name, it replaces the
    builtin path for that colleague while preserving builtin priority.
    """
    scanned: list[ColleagueInfo] = []
    root_path: Path | None = None
    if skill_root and skill_root.strip():
        root_path = Path(skill_root).expanduser()
        if root_path.is_dir():
            for d in iter_skill_dirs(root_path):
                meta = load_meta(d)
                slug = _slug_from_dir(d, meta)
                cid = slug
                scanned.append(
                    ColleagueInfo(
                        colleague_id=cid,
                        display_name=_name_from_meta(d, meta),
                        skill_path=d.resolve(),
                        is_builtin=False,
                    )
                )

    builtin_meta = load_meta(builtin_skill)
    builtin_slug = _slug_from_dir(builtin_skill, builtin_meta)
    builtin_name = _name_from_meta(builtin_skill, builtin_meta)
    builtin_dir_name = builtin_skill.name

    builtin_from_scan = next(
        (
            c
            for c in scanned
            if c.colleague_id == builtin_slug or c.skill_path.name == builtin_dir_name
        ),
        None,
    )

    if builtin_from_scan:
        rest = [c for c in scanned if c.skill_path != builtin_from_scan.skill_path]
        return [
            ColleagueInfo(
                colleague_id=builtin_from_scan.colleague_id,
                display_name=builtin_from_scan.display_name,
                skill_path=builtin_from_scan.skill_path,
                is_builtin=True,
            )
        ] + rest

    if not builtin_skill.is_dir() or not (builtin_skill / "SKILL.md").is_file():
        return list(scanned)

    builtin_colleague = ColleagueInfo(
        colleague_id=builtin_slug,
        display_name=builtin_name,
        skill_path=builtin_skill.resolve(),
        is_builtin=True,
    )
    return [builtin_colleague] + scanned
