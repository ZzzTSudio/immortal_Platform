"""Application and resource path resolution (dev vs PyInstaller)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    """Repository root (parent of `app/`, contains `skill_lib/` etc.)."""
    here = Path(__file__).resolve().parent
    return here.parent


def fangzheng_xiangli_font_path() -> Path:
    """主窗口标题「方正祥隶简体」TTF；开发为项目根下 fonts/，打包后为 _MEIPASS/fonts/。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "fonts" / "方正祥隶简体.TTF"
    return project_root() / "fonts" / "方正祥隶简体.TTF"


def default_colleague_icon_path() -> Path:
    """Bundled default avatar when a skill has no `icon/` image."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "pic" / "icon_default.png"
    return project_root() / "pic" / "icon_default.png"


def sticker_pack_dir() -> Path:
    """Folder of sticker images (`pic/bqb/`) for random chat stickers."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "pic" / "bqb"
    return project_root() / "pic" / "bqb"


def app_window_icon_path() -> Path:
    """主窗口与任务栏图标（pic/soft_icon/soft.ico）；打包后位于 _MEIPASS/pic/...。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "pic" / "soft_icon" / "soft.ico"
    return project_root() / "pic" / "soft_icon" / "soft.ico"


def app_logo_path() -> Path:
    """导航栏左上角应用标识图（pic/logo.png）；打包后与 pic/ 一并打入。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "pic" / "logo.png"
    return project_root() / "pic" / "logo.png"


def user_icon_path(settings: object | None = None) -> Path:
    """本地用户头像：优先使用设置里的自定义路径，否则为资源包 `pic/user_icon.png`。"""
    if settings is not None:
        custom = str(getattr(settings, "user_avatar_path", "") or "").strip()
        if custom:
            p = Path(custom)
            if p.is_file():
                return p.resolve()
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / "pic" / "user_icon.png"
    else:
        p = project_root() / "pic" / "user_icon.png"
    if p.is_file():
        return p
    return default_colleague_icon_path()


def builtin_skill_dir() -> Path:
    """Directory of the bundled default skill."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "fangdoudou-skill"
    return project_root() / "skill_lib" / "fangdoudou-skill"


def config_dir() -> Path:
    """User config directory for settings JSON."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path.home() / ".config"
    d = base / "CyberColleague"
    d.mkdir(parents=True, exist_ok=True)
    return d
