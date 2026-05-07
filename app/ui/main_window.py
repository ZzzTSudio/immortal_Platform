"""Main three-pane window: nav, colleagues, chat."""

from __future__ import annotations

import base64
import random
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QByteArray,
    QBuffer,
    QEvent,
    QIODevice,
    QObject,
    QPropertyAnimation,
    QEasingCurve,
    QStandardPaths,
    Qt,
    QSize,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.bracket_emoticons import substitute_bracket_emoticons
from app.markdown_plain import assistant_plain_for_display
from app.chat_history_store import (
    chat_histories_path,
    load_chat_histories,
    save_chat_histories,
)
from app.paths import (
    app_logo_path,
    builtin_skill_dir,
    config_dir,
    default_colleague_icon_path,
    sticker_pack_dir,
    user_icon_path,
)
from app.settings import AppSettings, DEFAULT_CHAT_FONT_SIZE
from app.skill_loader import (
    ColleagueInfo,
    build_system_prompt,
    colleague_id_for_dir,
    discover_colleagues,
    load_meta,
    resolve_colleague_icon,
    save_skill_display_name,
)
from app.ui.import_colleague_dialog import ImportColleagueNameDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.stream_worker import StreamWorker

# 与 QQ/微信类似：相邻两条消息间隔 ≥ 此秒数时，在中间插入居中时间分隔。
CHAT_TIME_GAP_SECONDS = 120
# 无消息时 QTextBrowser 占位；有本地记录且折叠时置空以免与顶栏折叠条重复提示。
_CHAT_VIEW_PLACEHOLDER = "选择左侧同事开始对话…"
# 会话区顶部热区：鼠标进入则滑入「展开/收起历史」条（仅当有启动前留存的历史时）
_CHAT_TOP_HOT_ZONE_PX = 72
_HISTORY_FOLD_BAR_ANIM_MS = 240
_HISTORY_FOLD_HIDE_DELAY_MS = 160
_HISTORY_FOLD_BAR_OPEN_PX = 44


class _ClickableNameLabel(QLabel):
    """用于同事列表中的显示名：左键双击发出信号（用于重命名）。"""

    doubleClicked = Signal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

# API 调用失败时，以同事口吻展示（不显示红色 [错误] 与技术栈信息）
_API_FAILURE_PEER_MESSAGE = "不是鸽们，你模型都没配置对还想找我聊天~先去查查api地址和密钥吧"
_NETWORK_FAILURE_PEER_MESSAGE = "网不好吧鸽们"

# 与页面风格一致：两侧栏固定宽度，仅右侧对话区随窗口伸缩
_NAV_WIDTH = 60
_SIDE_WIDTH = 200
_LIST_ICON_SIZE = 44
_LIST_ICON_RADIUS = 10
# 聊天区内表情包统一缩小显示（与头像列对齐）
_STICKER_CHAT_MAX_H = 88
_STICKER_CHAT_MAX_W = 110
# 对话气泡里头像尺寸（与 HTML 中 img 宽高一致）
_CHAT_ICON_SIZE = 40
_CHAT_ICON_RADIUS = 10
# 流式输出前插入占位符，定位 QTextCursor 后删除，再在此处 insertText
_STREAM_BODY_PLACEHOLDER = "__CYBER_STREAM_BODY__"
# 发送与「终止|刷新」分栏共用外框尺寸，避免纵向布局把分栏压窄
_SEND_ACTION_WIDTH = 112
_SEND_ACTION_HEIGHT = 36
_SEND_ACTION_SPACING = 8
_ACTION_BTN_FONT_SIZE = 14
_ACTION_BTN_FONT_WEIGHT = 720
# API 首包前的等待动画（单字符轮换，避免 QTextBrowser 对 CSS 动画支持差）
_STREAM_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_STREAM_SPINNER_INTERVAL_MS = 90
# 首包前文案由 llm_client / StreamWorker.status_changed 按真实阶段推送，此处仅为首帧默认
_STREAM_LOADING_DEFAULT_STATUS = "正在准备请求…"
# 仅在 API 成功返回本轮文字后插入；pic/bqb 无图片时 _pick_random_sticker_path 恒为 None
STICKER_ROLL_PROB = 0.25
# 气泡内文字与 QTextBrowser 流式插入共用；font-family 需带引号以支持含空格的字体名。
# 1️⃣2️⃣3️⃣ 等为 Unicode「键帽」组合序列，需让 Segoe UI Emoji 优先于雅黑等，否则易拆字成方框。
_CHAT_MSG_FONT_FAMILY = (
    "'Segoe UI Emoji','Segoe UI','Noto Color Emoji','Microsoft YaHei UI','PingFang SC','Apple Color Emoji'"
)

def _pixmap_to_png_data_url(pm: QPixmap) -> str:
    """将 QPixmap 转为 data:image/png;base64,...，供 QTextBrowser 使用。"""
    if pm.isNull():
        return ""
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    if not pm.save(buf, "PNG"):
        return ""
    return "data:image/png;base64," + base64.standard_b64encode(bytes(ba)).decode("ascii")


def _load_avatar_pixmap(icon_path: Path) -> QPixmap:
    p = icon_path.resolve()
    pm = QPixmap(str(p))
    if pm.isNull():
        pm = QPixmap(str(default_colleague_icon_path().resolve()))
    return pm


def _rounded_avatar_pixmap(icon_path: Path, size: int, radius: int) -> QPixmap:
    pm_raw = _load_avatar_pixmap(icon_path)
    if pm_raw.isNull():
        return QPixmap()

    scaled = pm_raw.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    square = scaled.copy(x, y, size, size)

    rounded = QPixmap(size, size)
    rounded.fill(Qt.GlobalColor.transparent)

    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, square)
    painter.end()
    return rounded


def _nav_brand_logo_pixmap(size: int) -> QPixmap:
    """主窗口导航区左上角 logo（pic/logo.png），按比例缩放至不超过 size。"""
    p = app_logo_path()
    pm = QPixmap(str(p))
    if pm.isNull():
        pm = QPixmap(str(default_colleague_icon_path()))
        if pm.isNull():
            return QPixmap()
    return pm.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _chat_avatar_data_url(icon_path: Path) -> str:
    """
    与侧栏列表一致：先用 QPixmap 解码再缩放，再写入 HTML。

    直接用 file:// 喂给 QTextDocument 时，部分 PNG 会出现暗部发灰/发白、与 QLabel 不一致；
    走与 QLabel 相同的像素管线可避免该问题。
    """
    p = icon_path.resolve()
    pm = _rounded_avatar_pixmap(p, _CHAT_ICON_SIZE, _CHAT_ICON_RADIUS)
    url = _pixmap_to_png_data_url(pm)
    if url:
        return url
    return QUrl.fromLocalFile(str(p)).toString()


def _sticker_image_data_url(path: Path) -> str:
    """
    表情包大图：与头像相同用 PNG data URL，避免 QTextDocument 对 file:// 图片不显示或异常。
    大图先按聊天区上限缩放，减小 base64 体积。
    """
    p = path.resolve()
    if not p.is_file():
        return ""
    pm = QPixmap(str(p))
    if pm.isNull():
        return ""
    if pm.width() > _STICKER_CHAT_MAX_W or pm.height() > _STICKER_CHAT_MAX_H:
        pm = pm.scaled(
            _STICKER_CHAT_MAX_W,
            _STICKER_CHAT_MAX_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return _pixmap_to_png_data_url(pm)


def _pick_random_sticker_path() -> Path | None:
    """Random image from ``pic/bqb`` (png/jpg/jpeg/gif/webp). 目录不存在或为空时返回 None。"""
    d = sticker_pack_dir()
    if not d.is_dir():
        return None
    files: list[Path] = []
    for pat in ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.PNG", "*.JPG", "*.JPEG"):
        files.extend(p for p in d.glob(pat) if p.is_file())
    if not files:
        return None
    return random.choice(files).resolve()


class MainWindow(QWidget):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.setWindowTitle(f"Immortal")
        self.setMinimumSize(800, 560)
        self.resize(960, 720)
        self._settings = settings
        self._colleagues: list[ColleagueInfo] = []
        self._current_id: str | None = None
        self._chat_histories_path = chat_histories_path(config_dir())
        self._histories: dict[str, list[dict[str, Any]]] = load_chat_histories(
            self._chat_histories_path
        )
        # 各同事「历史」与「本次会话」分界：启动时本地已有条数；仅下标 < 分界 属于历史聊天记录。
        self._hist_session_boundary: dict[str, int] = {
            cid: len(mlist) for cid, mlist in self._histories.items()
        }
        self._system_cache: dict[str, str] = {}
        self._worker: StreamWorker | None = None
        self._streaming_buffer = ""
        # 流式回复时，文本插入到占位符处，使头像与首字同时出现
        self._stream_insert_cursor: QTextCursor | None = None
        self._stream_loading_timer: QTimer | None = None
        self._stream_loading_anchor: int | None = None
        self._stream_loading_frame: int = 0
        self._stream_loading_text: str = ""
        self._stream_loading_status_message: str = _STREAM_LOADING_DEFAULT_STATUS
        self._pending_session_reset: bool = False
        # 用户点终止后为 True，忽略可能排队迟到的 chunk，避免界面已重绘又被写入
        self._suppress_stream_chunks: bool = False
        # 当前流式请求所属同事（与左侧选中可能不同：切走后仍归属原会话）
        self._streaming_colleague_id: str | None = None
        # 流式正文在 QTextDocument 中的区间，用于整段替换为「去 Markdown」后的纯文本
        self._stream_plain_start: int | None = None
        self._stream_plain_end: int | None = None
        # 本次运行期间已「展开历史」的同事 id（仅影响启动前留存部分）；重启后清空。
        self._history_expanded_ids: set[str] = set()
        self._history_fold_hide_timer = QTimer(self)
        self._history_fold_hide_timer.setSingleShot(True)
        self._history_fold_hide_timer.setInterval(_HISTORY_FOLD_HIDE_DELAY_MS)
        self._history_fold_hide_timer.timeout.connect(self._hide_history_fold_bar_animated)
        self._history_fold_anim: QPropertyAnimation | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._nav = self._build_nav()
        self._side = self._build_side_bar()
        self._chat = self._build_chat_pane()

        self._nav.setFixedWidth(_NAV_WIDTH)
        self._nav.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._side.setFixedWidth(_SIDE_WIDTH)
        self._side.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        root.addWidget(self._nav)
        root.addWidget(self._side)
        root.addWidget(self._chat, stretch=1)

        self._apply_styles()
        self._refresh_colleagues()
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget { color: #1a1a1a; }
            QFrame#NavBar {
                background-color: #f0f0f0;
                border: none;
                border-right: 1px solid #e8e8e8;
            }
            QFrame#SideBar {
                background-color: #ffffff;
                border: none;
                border-right: 1px solid #eeeeee;
            }
            QFrame#ChatPane { background-color: #ffffff; border: none; }
            QFrame#ChatPane QLabel { background: transparent; }
            QLineEdit, QTextEdit, QPushButton, QListWidget, QCheckBox {
                font-size: 14px;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #e2e4e8; border-radius: 12px; padding: 10px 12px;
                background: #fff;
            }
            QPushButton {
                border-radius: 10px; padding: 8px 14px; border: none;
                background: #fff; color: #333;
            }
            QPushButton:hover { background: #e8eaef; }
            QWidget#SplitStopRefresh {
                background: transparent;
            }
            QWidget#ActionRail {
                background: transparent;
            }
            QWidget#WebSearchRow {
                background: transparent;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            /* 与 Send 同外框总宽；宽度由布局均分，勿写死 max-width 以免被压窄 */
            QPushButton#StopStreamBtn {
                color: white;
                font-size: %dpx;
                font-weight: %d;
                min-height: 36px;
                max-height: 36px;
                padding: 0px;
                border: none;
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-right: 1px solid rgba(0, 0, 0, 0.2);
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #556f95, stop:1 #415a7d);
            }
            QPushButton#RefreshSessionBtn {
                color: white;
                font-size: %dpx;
                font-weight: %d;
                min-height: 36px;
                max-height: 36px;
                padding: 0px;
                border: none;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #556f95, stop:1 #415a7d);
            }
            QPushButton#StopStreamBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5f7899, stop:1 #4a6288);
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-right: 1px solid rgba(0, 0, 0, 0.2);
            }
            QPushButton#RefreshSessionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5f7899, stop:1 #4a6288);
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
            }
            QPushButton#StopStreamBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d5065, stop:1 #4c6a92);
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
                border-right: 1px solid rgba(0, 0, 0, 0.2);
            }
            QPushButton#RefreshSessionBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d5065, stop:1 #4c6a92);
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QPushButton#StopStreamBtn:disabled {
                color: #9ca3af;
                border: none;
                border-right: 1px solid rgba(0, 0, 0, 0.15);
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a6288, stop:1 #445a7a);
            }
            QPushButton#SendBtn {
                color: white;
                font-size: %dpx;
                font-weight: %d;
                min-width: 112px;
                max-width: 112px;
                min-height: 36px;
                max-height: 36px;
                border-radius: 8px;
                padding: 0px;
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #556f95, stop:1 #415a7d);
            }
            QPushButton#SendBtn:hover {
                border-radius: 8px;
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5f7899, stop:1 #4a6288);
            }
            QPushButton#SendBtn:pressed {
                border-radius: 8px;
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d5065, stop:1 #4c6a92);
            }
            QPushButton#SettingsBtn {
                background: transparent; color: #6b7280;
                font-size: 26px; min-width: 48px; max-width: 48px;
                min-height: 48px; max-height: 48px; padding: 0;
                border: none; outline: none;
            }
            QPushButton#SettingsBtn:hover {
                background: #e5e7eb; color: #374151;
                border: none; outline: none;
            }
            QPushButton#SettingsBtn:pressed {
                border: none; outline: none;
            }
            QListWidget { border: none; background: transparent; outline: none; }
            QListWidget::item {
                padding: 0; border-radius: 10px;
                color: #000000;
            }
            QListWidget::item:selected {
                background: #e8eef5;
                color: #000000;
            }
            QListWidget::item:hover { background: #f3f4f6; }
            QLabel#Disclaimer { color: #9ca3af; font-size: 11px; }
            QPushButton#ColleagueDelBtn {
                background: transparent; border: none; color: #9ca3af;
                font-size: 18px; font-weight: 600; padding: 0;
            }
            QPushButton#ColleagueDelBtn:hover { color: #ef4444; background: #fee2e2; border-radius: 6px; }

            QCheckBox#WebSearchToggle { spacing: 0; background: transparent; }
            QCheckBox#WebSearchToggle::indicator {
                width: 10px; height: 10px; border-radius: 5px;
                border: 1px solid #5c6570;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f9fafb, stop:1 #e5e7eb);
            }
            QCheckBox#WebSearchToggle::indicator:hover {
                border: 1px solid #4c6a92;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #eceef2);
            }
            QCheckBox#WebSearchToggle::indicator:checked {
                border: 1px solid #3a4d63;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #556f95, stop:1 #415a7d);
            }
            QCheckBox#WebSearchToggle::indicator:checked:hover {
                border: 1px solid #3d5065;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5f7899, stop:1 #4a6288);
            }
            QLabel#WebSearchLabel {
                color: #6b7280; font-size: 12px; background: transparent;
                font-weight: 500;
            }

            QFrame#HistoryFoldBar { background: transparent; }
            QPushButton#HistoryFoldBtn {
                color: #6b7280;
                font-size: 12px;
                background-color: #e6e8eb;
                border: none;
                border-radius: 12px;
                padding: 4px 12px;
            }
            QPushButton#HistoryFoldBtn:hover { background-color: #dce0e6; }
            QPushButton#HistoryFoldBtn:pressed { background-color: #cdd2d9; }

            /* 聊天区与同事列表滚动条：同套细轨道、圆角滑块 */
            QTextBrowser#ChatView {
                background: #ffffff;
            }
            QTextBrowser#ChatView QScrollBar:vertical,
            QListWidget QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 10px;
                margin: 6px 4px 6px 0;
            }
            QTextBrowser#ChatView QScrollBar::handle:vertical,
            QListWidget QScrollBar::handle:vertical {
                background: #d1d5db;
                border-radius: 5px;
                min-height: 36px;
            }
            QTextBrowser#ChatView QScrollBar::handle:vertical:hover,
            QListWidget QScrollBar::handle:vertical:hover {
                background: #9ca3af;
            }
            QTextBrowser#ChatView QScrollBar::handle:vertical:pressed,
            QListWidget QScrollBar::handle:vertical:pressed {
                background: #6b7280;
            }
            QTextBrowser#ChatView QScrollBar::add-line:vertical,
            QTextBrowser#ChatView QScrollBar::sub-line:vertical,
            QListWidget QScrollBar::add-line:vertical,
            QListWidget QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0;
            }
            QTextBrowser#ChatView QScrollBar::add-page:vertical,
            QTextBrowser#ChatView QScrollBar::sub-page:vertical,
            QListWidget QScrollBar::add-page:vertical,
            QListWidget QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QTextBrowser#ChatView QScrollBar:horizontal,
            QListWidget QScrollBar:horizontal {
                border: none;
                background: transparent;
                height: 10px;
                margin: 0 6px 4px 6px;
            }
            QTextBrowser#ChatView QScrollBar::handle:horizontal,
            QListWidget QScrollBar::handle:horizontal {
                background: #d1d5db;
                border-radius: 5px;
                min-width: 36px;
            }
            QTextBrowser#ChatView QScrollBar::handle:horizontal:hover,
            QListWidget QScrollBar::handle:horizontal:hover {
                background: #9ca3af;
            }
            QTextBrowser#ChatView QScrollBar::add-line:horizontal,
            QTextBrowser#ChatView QScrollBar::sub-line:horizontal,
            QListWidget QScrollBar::add-line:horizontal,
            QListWidget QScrollBar::sub-line:horizontal {
                border: none;
                background: none;
                width: 0;
            }
            QTextBrowser#ChatView QScrollBar::add-page:horizontal,
            QTextBrowser#ChatView QScrollBar::sub-page:horizontal,
            QListWidget QScrollBar::add-page:horizontal,
            QListWidget QScrollBar::sub-page:horizontal {
                background: transparent;
            }
            """
            % (
                _ACTION_BTN_FONT_SIZE,
                _ACTION_BTN_FONT_WEIGHT,
                _ACTION_BTN_FONT_SIZE,
                _ACTION_BTN_FONT_WEIGHT,
                _ACTION_BTN_FONT_SIZE,
                _ACTION_BTN_FONT_WEIGHT,
            )
        )

    def _build_nav(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("NavBar")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(16)

        logo_lbl = QLabel()
        self._nav_logo_label = logo_lbl
        logo_lbl.setFixedSize(_CHAT_ICON_SIZE, _CHAT_ICON_SIZE)
        logo_lbl.setPixmap(_nav_brand_logo_pixmap(_CHAT_ICON_SIZE))
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet("background: transparent; border: none;")
        logo_lbl.setScaledContents(False)
        layout.addWidget(logo_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("SettingsBtn")
        settings_btn.setToolTip("设置")
        settings_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        return frame

    def _build_side_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SideBar")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(12)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索")
        self._search.textChanged.connect(self._filter_colleagues)
        layout.addWidget(self._search)

        add_btn = QPushButton("+ 新建同事")
        add_btn.clicked.connect(self._add_colleague)
        layout.addWidget(add_btn)

        self._list = QListWidget()
        self._list.setIconSize(QSize(_LIST_ICON_SIZE, _LIST_ICON_SIZE))
        self._list.currentItemChanged.connect(self._on_colleague_changed)
        layout.addWidget(self._list, stretch=1)
        return frame

    def _build_chat_pane(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ChatPane")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(8)

        # 仅控制「启动前留存的历史」展开/收起；默认高度 0，鼠标移入会话区顶部热区后滑入
        self._history_fold_bar = QFrame()
        self._history_fold_bar.setObjectName("HistoryFoldBar")
        fold_outer = QHBoxLayout(self._history_fold_bar)
        fold_outer.setContentsMargins(0, 0, 0, 0)
        fold_outer.addStretch()
        self._history_fold_btn = QPushButton("")
        self._history_fold_btn.setObjectName("HistoryFoldBtn")
        self._history_fold_btn.setFlat(True)
        self._history_fold_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._history_fold_btn.setToolTip(
            "展开或收起本次启动前已保存的历史记录；本次运行中的对话始终在下面显示。"
        )
        self._history_fold_btn.clicked.connect(self._on_history_fold_bar_clicked)
        fold_outer.addWidget(self._history_fold_btn)
        fold_outer.addStretch()
        self._history_fold_bar.setMaximumHeight(0)
        self._history_fold_bar.setMinimumHeight(0)
        self._history_fold_bar.show()
        layout.addWidget(self._history_fold_bar)
        self._history_fold_bar.installEventFilter(self)

        self._chat_view = QTextBrowser()
        self._chat_view.setObjectName("ChatView")
        self._chat_view.setReadOnly(True)
        self._chat_view.setOpenExternalLinks(False)
        self._chat_view.setOpenLinks(False)
        _chat_font = self._emoji_capable_font()
        self._chat_view.setFont(_chat_font)
        self._chat_view.document().setDefaultFont(_chat_font)
        self._chat_view.setPlaceholderText(_CHAT_VIEW_PLACEHOLDER)
        # 无按键移动也要收到 MouseMove，否则离开顶部热区无法触发收起计时（默认 mouseTracking 为 false）
        self._chat_view.setMouseTracking(True)
        self._chat_viewport = self._chat_view.viewport()
        self._chat_viewport.setMouseTracking(True)
        self._chat_viewport.installEventFilter(self)
        self._chat_view.installEventFilter(self)
        layout.addWidget(self._chat_view, stretch=1)

        input_row = QHBoxLayout()
        input_row.setSpacing(12)
        self._input = QTextEdit()
        self._input.setFont(_chat_font)
        self._input.setPlaceholderText("输入消息，Enter 发送，Shift+Enter 换行")
        self._input.setMaximumHeight(120)
        self._input.installEventFilter(self)
        self._refresh_session_btn = QPushButton("⟳")
        self._refresh_session_btn.setObjectName("RefreshSessionBtn")
        self._refresh_session_btn.setFixedHeight(_SEND_ACTION_HEIGHT)
        self._refresh_session_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._refresh_session_btn.setToolTip(
            "新会话：清除本同事对话与缓存（含本地保存的聊天记录），重新开始"
        )
        self._refresh_session_btn.clicked.connect(self._on_refresh_session_clicked)
        self._stop_stream_btn = QPushButton("■")
        self._stop_stream_btn.setObjectName("StopStreamBtn")
        self._stop_stream_btn.setFixedHeight(_SEND_ACTION_HEIGHT)
        self._stop_stream_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._stop_stream_btn.setToolTip("停止生成")
        self._stop_stream_btn.setEnabled(False)
        self._stop_stream_btn.clicked.connect(self._stop_streaming)
        send = QPushButton("➤")
        send.setObjectName("SendBtn")
        send.setFixedHeight(_SEND_ACTION_HEIGHT)
        send.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        send.setToolTip("发送")
        send.clicked.connect(self._send_message)
        input_row.addWidget(self._input, stretch=1)
        action_rail = QWidget()
        action_rail.setObjectName("ActionRail")
        action_rail.setFixedWidth(_SEND_ACTION_WIDTH)
        send_col = QVBoxLayout(action_rail)
        send_col.setContentsMargins(0, 0, 0, 0)
        send_col.setSpacing(_SEND_ACTION_SPACING)
        split_stop_refresh = QWidget()
        split_stop_refresh.setObjectName("SplitStopRefresh")
        split_stop_refresh.setFixedHeight(_SEND_ACTION_HEIGHT)
        split_stop_refresh.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        split_lay = QHBoxLayout(split_stop_refresh)
        split_lay.setContentsMargins(0, 0, 0, 0)
        split_lay.setSpacing(0)
        split_lay.addWidget(self._stop_stream_btn, stretch=1)
        split_lay.addWidget(self._refresh_session_btn, stretch=1)
        web_row = QWidget()
        web_row.setObjectName("WebSearchRow")
        web_row.setFixedHeight(32)
        web_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        web_row_lay = QHBoxLayout(web_row)
        web_row_lay.setContentsMargins(10, 0, 10, 0)
        web_row_lay.setSpacing(8)
        self._web_search_toggle = QCheckBox()
        self._web_search_toggle.setObjectName("WebSearchToggle")
        self._web_search_toggle.setChecked(False)
        web_lbl = QLabel("联网搜索")
        web_lbl.setObjectName("WebSearchLabel")
        web_row_lay.addStretch(1)
        web_row_lay.addWidget(self._web_search_toggle, alignment=Qt.AlignmentFlag.AlignVCenter)
        web_row_lay.addWidget(web_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        web_row_lay.addStretch(1)
        web_row.setToolTip(
            "开启后，每次发送前会将你的问题发往 Ollama 联网检索；摘要仅用于本轮模型请求，"
            "不会显示在聊天记录中。关闭则与平时一致。"
            "检索地址与密钥在「设置 → 联网设置」中配置。"
        )
        send_col.addWidget(web_row)
        send_col.addWidget(split_stop_refresh)
        send_col.addWidget(send)
        input_row.addWidget(action_rail, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(input_row)

        disclaimer = QLabel(
            "内容由AI生成，请仔细甄别。"
            "软件作者：ZzzT，BUG反馈请联系：993895373@qq.com。"
        )
        disclaimer.setObjectName("Disclaimer")
        disclaimer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(disclaimer)
        return frame

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is getattr(self, "_input", None) and event.type() == QEvent.Type.KeyPress:
            ke = event
            if isinstance(ke, QKeyEvent):
                if ke.key() == Qt.Key.Key_Return and ke.modifiers() == Qt.KeyboardModifier.NoModifier:
                    self._send_message()
                    return True
        _cv = getattr(self, "_chat_view", None)
        _vp = getattr(self, "_chat_viewport", None)
        if obj is _cv or obj is _vp:
            et = event.type()
            # 内容区事件多在 viewport 上；坐标相对各自控件，热区用 y 即可
            if et == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
                if self._history_fold_should_show_toggle():
                    if event.position().y() < _CHAT_TOP_HOT_ZONE_PX:
                        if self._history_fold_bar.maximumHeight() < _HISTORY_FOLD_BAR_OPEN_PX - 2:
                            self._reveal_history_fold_bar()
                        self._history_fold_hide_timer.stop()
                    else:
                        if not self._history_fold_bar.underMouse():
                            self._history_fold_hide_timer.start()
            elif et == QEvent.Type.Leave:
                if not self._history_fold_bar.underMouse():
                    self._history_fold_hide_timer.start()
        if obj is getattr(self, "_history_fold_bar", None):
            if event.type() == QEvent.Type.Enter:
                self._history_fold_hide_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                self._history_fold_hide_timer.start()
        return super().eventFilter(obj, event)

    def _chat_font_point_size(self) -> int:
        v = int(getattr(self._settings, "chat_font_size", DEFAULT_CHAT_FONT_SIZE) or DEFAULT_CHAT_FONT_SIZE)
        return max(6, min(36, v))

    def _apply_chat_font_from_settings(self) -> None:
        f = self._emoji_capable_font()
        self._chat_view.setFont(f)
        self._chat_view.document().setDefaultFont(f)
        self._input.setFont(f)
        self._render_history()

    def _emoji_capable_font(self) -> QFont:
        """与气泡 HTML 一致：Emoji/键帽序列优先走 Segoe UI Emoji，再回退正文与中文。"""
        f = QFont()
        f.setPointSize(self._chat_font_point_size())
        f.setFamilies(
            [
                "Segoe UI Emoji",
                "Segoe UI",
                "Noto Color Emoji",
                "Microsoft YaHei UI",
                "PingFang SC",
                "Apple Color Emoji",
            ]
        )
        return f

    def _apply_stream_text_char_format(self, cur: QTextCursor) -> None:
        """流式 insertText 前合并格式，否则易继承 QTextDocument 默认字体导致 emoji 像纯文本。"""
        fmt = QTextCharFormat()
        fmt.setFont(self._emoji_capable_font())
        cur.mergeCharFormat(fmt)

    def _apply_stream_loading_char_format(self, cur: QTextCursor) -> None:
        fmt = QTextCharFormat()
        fmt.setFont(self._emoji_capable_font())
        fmt.setForeground(QColor("#9ca3af"))
        cur.mergeCharFormat(fmt)

    def _stream_loading_display_text(self) -> str:
        spinner = _STREAM_SPINNER_FRAMES[self._stream_loading_frame % len(_STREAM_SPINNER_FRAMES)]
        return f"{spinner} {self._stream_loading_status_message}"

    def _on_stream_remote_status(self, message: str) -> None:
        """后台线程经 Signal 传入的实时阶段说明；仅刷新首包前那一行文案。"""
        if (
            self._streaming_colleague_id is None
            or self._streaming_colleague_id != self._current_id
        ):
            return
        if self._stream_loading_status_message == message:
            return
        self._stream_loading_status_message = message
        if self._stream_loading_timer is None or self._stream_loading_anchor is None:
            return
        self._update_stream_loading_line(advance_spinner=False)

    def _open_settings(self, initial_page: int = 0) -> None:
        dlg = SettingsDialog(self._settings, self, initial_page=initial_page)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_colleagues()
            self._apply_chat_font_from_settings()

    def _build_colleague_row(self, c: ColleagueInfo) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(4, 6, 4, 6)
        lay.setSpacing(8)
        ip = resolve_colleague_icon(c.skill_path)
        scaled = _rounded_avatar_pixmap(ip, _LIST_ICON_SIZE, _LIST_ICON_RADIUS)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(_LIST_ICON_SIZE, _LIST_ICON_SIZE)
        icon_lbl.setPixmap(scaled)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        cid = c.colleague_id
        if c.is_builtin:
            name_lbl = QLabel(c.display_name)
            name_lbl.setStyleSheet("color: #000000;")
            name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        else:
            name_lbl = _ClickableNameLabel(c.display_name)
            name_lbl.setStyleSheet("color: #000000;")
            name_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            name_lbl.setToolTip("双击修改显示名称")
            name_lbl.doubleClicked.connect(lambda _=False, i=cid: self._rename_colleague(i))
        lay.addWidget(icon_lbl)
        lay.addWidget(name_lbl, stretch=1)
        del_btn = QPushButton("×")
        del_btn.setObjectName("ColleagueDelBtn")
        del_btn.setFixedSize(26, 26)
        del_btn.setToolTip("从列表中移除（不删除磁盘上的 Skill）")
        del_btn.clicked.connect(lambda _=False, i=cid: self._confirm_delete_colleague(i))
        lay.addWidget(del_btn)
        if c.is_builtin:
            del_btn.hide()
            del_btn.setEnabled(False)
        return row

    def _confirm_delete_colleague(self, colleague_id: str) -> None:
        c = next((x for x in self._colleagues if x.colleague_id == colleague_id), None)
        if not c:
            return
        if c.is_builtin:
            QMessageBox.information(self, "提示", f"「{c.display_name}」为内置同事，不可移除。")
            return
        r = QMessageBox.question(
            self,
            "嗯？要赶我走？",
            f"确定开除「{c.display_name}」吗？\n"
            "Big胆！！竟然我离职之后还要再开除我的赛博分身。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        hidden = self._settings.hidden_colleague_ids
        if colleague_id not in hidden:
            hidden = [*hidden, colleague_id]
            self._settings.hidden_colleague_ids = hidden
            self._settings.save()
        self._system_cache.pop(str(c.skill_path), None)
        if self._current_id == colleague_id:
            self._current_id = None
        self._refresh_colleagues()

    def _rename_colleague(self, colleague_id: str) -> None:
        c = next((x for x in self._colleagues if x.colleague_id == colleague_id), None)
        if not c:
            return
        if c.is_builtin:
            QMessageBox.information(self, "提示", f"「{c.display_name}」为内置同事，不可改名。")
            return
        self._select_colleague_by_id(colleague_id)
        dlg = ImportColleagueNameDialog(
            c.display_name,
            self,
            window_title="重命名同事",
            prompt="显示名称（最多 8 个字）：",
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_name = dlg.display_name()
        if new_name == c.display_name:
            return
        save_skill_display_name(c.skill_path, new_name)
        self._system_cache.pop(str(c.skill_path), None)
        self._refresh_colleagues()
        self._select_colleague_by_id(colleague_id)

    def _unhide_colleague_for_skill_dir(self, skill_dir: Path) -> None:
        """新建/更新同事时若该 slug 曾被隐藏，则重新显示。"""
        cid = colleague_id_for_dir(skill_dir)
        if cid in self._settings.hidden_colleague_ids:
            self._settings.hidden_colleague_ids = [x for x in self._settings.hidden_colleague_ids if x != cid]
            self._settings.save()

    def _refresh_colleagues(self) -> None:
        prev_id = self._current_id
        builtin = builtin_skill_dir()
        all_c = discover_colleagues(self._settings.skill_root_path, builtin)
        builtin_ids = {c.colleague_id for c in all_c if c.is_builtin}
        hidden_ids = [cid for cid in self._settings.hidden_colleague_ids if cid not in builtin_ids]
        if hidden_ids != self._settings.hidden_colleague_ids:
            self._settings.hidden_colleague_ids = hidden_ids
            self._settings.save()
        hide = set(hidden_ids)
        self._colleagues = [c for c in all_c if c.colleague_id not in hide]
        self._list.clear()
        for c in self._colleagues:
            item = QListWidgetItem()
            item.setText("")
            item.setData(Qt.ItemDataRole.UserRole, c.colleague_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, c.display_name)
            row = self._build_colleague_row(c)
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
            item.setSizeHint(row.sizeHint())
        self._filter_colleagues()
        ids = [c.colleague_id for c in self._colleagues]
        if prev_id and prev_id in ids:
            self._select_colleague_by_id(prev_id)
        elif self._current_id and self._current_id not in ids:
            self._current_id = None
        if self._list.count() > 0 and self._current_id is None:
            self._list.setCurrentRow(0)

    def _filter_colleagues(self) -> None:
        q = self._search.text().strip().lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            text = str(item.data(Qt.ItemDataRole.UserRole + 1) or "").lower()
            item.setHidden(bool(q) and q not in text)

    def _on_colleague_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if not current:
            return
        cid = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(cid, str):
            return
        # 切换会话时先停掉转圈定时器并清空无效锚点，避免进度条写到新会话文档里
        self._cancel_stream_loading_only()
        self._stream_insert_cursor = None
        self._stream_plain_start = None
        self._stream_plain_end = None
        self._current_id = cid
        self._render_history()
        self._resume_streaming_ui_if_needed()

    def _resume_streaming_ui_if_needed(self) -> None:
        """切回仍有流式任务进行中的同事时，恢复转圈进度或已输出的部分正文。"""
        if self._streaming_colleague_id is None or self._streaming_colleague_id != self._current_id:
            return
        if not self._worker or not self._worker.isRunning():
            return
        c = self._get_current_colleague()
        if not c:
            return
        peer_u = _chat_avatar_data_url(resolve_colleague_icon(c.skill_path))
        buf = self._streaming_buffer or ""
        if buf.strip():
            self._chat_view.append(
                self._assistant_row_html(peer_u, _STREAM_BODY_PLACEHOLDER)
            )
            cur = self._prepare_stream_insert_cursor(_STREAM_BODY_PLACEHOLDER)
            self._stream_insert_cursor = cur
            if cur is not None and not cur.isNull():
                a = cur.position()
                plain = assistant_plain_for_display(buf)
                self._apply_stream_text_char_format(cur)
                cur.insertText(plain)
                self._stream_plain_start = a
                self._stream_plain_end = cur.position()
        else:
            self._chat_view.append(self._assistant_row_html(peer_u, _STREAM_BODY_PLACEHOLDER))
            self._stream_insert_cursor = self._prepare_stream_insert_cursor(_STREAM_BODY_PLACEHOLDER)
            if self._stream_insert_cursor:
                self._begin_stream_loading(preserve_status_message=True)
        sb = self._chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _get_current_colleague(self) -> ColleagueInfo | None:
        if not self._current_id:
            return None
        for c in self._colleagues:
            if c.colleague_id == self._current_id:
                return c
        return None

    def _colleague_by_id(self, colleague_id: str | None) -> ColleagueInfo | None:
        if not colleague_id:
            return None
        for c in self._colleagues:
            if c.colleague_id == colleague_id:
                return c
        return None

    def _system_prompt_for(self, c: ColleagueInfo) -> str:
        key = str(c.skill_path)
        if key not in self._system_cache:
            self._system_cache[key] = build_system_prompt(c.skill_path)
        return self._system_cache[key]

    def _icon_file_url(self, path: Path) -> str:
        return QUrl.fromLocalFile(str(path.resolve())).toString()

    def _user_row_html(self, user_icon_url: str, content: str) -> str:
        """User messages: text + avatar, aligned right (no \"你\" label)."""
        pt = self._chat_font_point_size()
        return (
            "<table width='100%' cellspacing='0' cellpadding='0' style='margin-bottom:12px;'><tr>"
            "<td align='right'>"
            "<table cellspacing='0' cellpadding='0' align='right'><tr>"
            f"<td valign='top' style='padding-right:10px; text-align:right; max-width:520px; color:#1a1a1a; font-size:{pt}pt; font-family:{_CHAT_MSG_FONT_FAMILY};'>"
            f"{_escape_html(content)}</td>"
            f"<td valign='top'><img src=\"{user_icon_url}\" width=\"40\" height=\"40\" style='border-radius:20px;'/></td>"
            "</tr></table></td></tr></table>"
        )

    def _assistant_row_html(self, icon_url: str, content: str) -> str:
        """Assistant messages: avatar + text, aligned left (no \"同事\" label)."""
        pt = self._chat_font_point_size()
        return (
            "<table width='100%' cellspacing='0' cellpadding='0' style='margin-bottom:12px;'><tr>"
            "<td align='left'>"
            "<table cellspacing='0' cellpadding='0' align='left'><tr>"
            f"<td valign='top' style='padding-right:10px;'>"
            f"<img src=\"{icon_url}\" width=\"40\" height=\"40\" style='border-radius:20px;'/></td>"
            f"<td valign='top' style='text-align:left; max-width:520px; color:#1a1a1a; font-size:{pt}pt; font-family:{_CHAT_MSG_FONT_FAMILY};'>{_escape_html(content)}</td>"
            "</tr></table></td></tr></table>"
        )

    def _chat_time_separator_html(self, ts: float) -> str:
        label = _format_chat_timestamp(ts)
        pt = self._chat_font_point_size()
        return (
            "<table width='100%' cellspacing='0' cellpadding='0' style='margin-bottom:8px;'><tr>"
            "<td align='center' style='padding:4px 0 8px 0;'>"
            f"<span style='display:inline-block;background-color:#e6e8eb;color:#8b9099;font-size:{pt}pt;"
            f"font-family:{_CHAT_MSG_FONT_FAMILY};padding:4px 12px;border-radius:12px;'>"
            f"{_escape_html(label)}</span>"
            "</td></tr></table>"
        )

    def _sticker_bubble_html(self, image_path_str: str, peer_icon_url: str) -> str:
        """表情包：与同事消息相同（左侧同事头像 + 右侧小图），不占太大版面。"""
        p = Path(image_path_str).expanduser().resolve()
        if not p.is_file():
            return ""
        url = _sticker_image_data_url(p)
        if not url:
            url = self._icon_file_url(p)
        return (
            "<table width='100%' cellspacing='0' cellpadding='0' style='margin-bottom:10px;'><tr>"
            "<td align='left'>"
            "<table cellspacing='0' cellpadding='0' align='left'><tr>"
            f"<td valign='top' style='padding-right:10px;'>"
            f"<img src=\"{peer_icon_url}\" width=\"40\" height=\"40\" style='border-radius:20px;'/></td>"
            f"<td valign='middle' style='text-align:left;'>"
            f"<img src=\"{url}\" style=\"max-height:{_STICKER_CHAT_MAX_H}px;max-width:{_STICKER_CHAT_MAX_W}px;"
            "height:auto;width:auto;border-radius:8px;\"/>"
            "</td></tr></table></td></tr></table>"
        )

    def _persist_chat_histories(self) -> None:
        try:
            save_chat_histories(self._chat_histories_path, self._histories)
        except OSError:
            pass

    def _hist_boundary(self, colleague_id: str) -> int:
        """启动时本地已有条数；下标 < 分界 的消息为「历史聊天记录」，之后为本次运行会话。"""
        if colleague_id not in self._hist_session_boundary:
            self._hist_session_boundary[colleague_id] = len(self._histories.get(colleague_id, []))
        return self._hist_session_boundary[colleague_id]

    def _history_fold_should_show_toggle(self) -> bool:
        if not self._current_id:
            return False
        return self._hist_boundary(self._current_id) > 0

    def _animate_history_fold_height(self, end_h: int) -> None:
        w = self._history_fold_bar
        if self._history_fold_anim is not None:
            self._history_fold_anim.stop()
            self._history_fold_anim.deleteLater()
            self._history_fold_anim = None
        start_h = w.maximumHeight()
        if start_h == end_h:
            w.setMaximumHeight(end_h)
            w.setMinimumHeight(0)
            return
        anim = QPropertyAnimation(w, b"maximumHeight", self)
        anim.setDuration(_HISTORY_FOLD_BAR_ANIM_MS)
        anim.setStartValue(start_h)
        anim.setEndValue(end_h)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._history_fold_anim = anim

        def _done() -> None:
            self._history_fold_anim = None
            w.setMinimumHeight(0)
            w.setMaximumHeight(end_h)

        anim.finished.connect(_done)
        anim.start()

    def _reveal_history_fold_bar(self) -> None:
        if not self._history_fold_should_show_toggle():
            return
        self._animate_history_fold_height(_HISTORY_FOLD_BAR_OPEN_PX)

    def _hide_history_fold_bar_animated(self) -> None:
        if self._history_fold_bar.underMouse():
            return
        self._animate_history_fold_height(0)

    def _update_history_fold_bar(self, has_pre_session_hist: bool) -> None:
        """有「启动前历史」时更新按钮文案；条高度默认 0，鼠标移入会话顶区后滑入。"""
        self._history_fold_hide_timer.stop()
        if self._history_fold_anim is not None:
            self._history_fold_anim.stop()
            self._history_fold_anim.deleteLater()
            self._history_fold_anim = None
        self._history_fold_bar.setMaximumHeight(0)
        self._history_fold_bar.setMinimumHeight(0)
        if not self._current_id or not has_pre_session_hist:
            return
        expanded = self._current_id in self._history_expanded_ids
        self._history_fold_btn.setText(
            "▽收起历史聊天记录" if expanded else "△展开历史聊天记录"
        )

    def _on_history_fold_bar_clicked(self) -> None:
        if self._current_id is None:
            return
        if self._hist_boundary(self._current_id) <= 0:
            return
        expanded = self._current_id in self._history_expanded_ids
        if expanded:
            self._history_expanded_ids.discard(self._current_id)
        else:
            self._history_expanded_ids.add(self._current_id)
        self._render_history()
        # 重绘会 clear 聊天区；若本同事仍有流式生成，恢复占位与已输出内容（与切换会话逻辑一致）
        self._resume_streaming_ui_if_needed()
        sb = self._chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _render_history(self) -> None:
        self._chat_view.clear()
        if not self._current_id:
            self._update_history_fold_bar(False)
            self._chat_view.setPlaceholderText(_CHAT_VIEW_PLACEHOLDER)
            return
        c = self._get_current_colleague()
        if not c:
            self._update_history_fold_bar(False)
            self._chat_view.setPlaceholderText(_CHAT_VIEW_PLACEHOLDER)
            return
        user_u = _chat_avatar_data_url(user_icon_path(self._settings))
        peer_u = _chat_avatar_data_url(resolve_colleague_icon(c.skill_path))
        msgs = self._histories.get(self._current_id, [])
        b = self._hist_boundary(self._current_id)
        hist_len = min(b, len(msgs))
        has_hist = hist_len > 0
        self._update_history_fold_bar(has_hist)

        if has_hist and self._current_id not in self._history_expanded_ids:
            to_render = msgs[hist_len:]
        else:
            to_render = msgs

        if not to_render:
            if has_hist and self._current_id not in self._history_expanded_ids:
                self._chat_view.setPlaceholderText("")
            else:
                self._chat_view.setPlaceholderText(_CHAT_VIEW_PLACEHOLDER)
            sb = self._chat_view.verticalScrollBar()
            sb.setValue(sb.maximum())
            return

        self._chat_view.setPlaceholderText(_CHAT_VIEW_PLACEHOLDER)
        prev_msg_ts: float | None = None
        for m in to_render:
            ts = m.get("ts")
            if isinstance(ts, (int, float)):
                tf = float(ts)
                if prev_msg_ts is None or tf - prev_msg_ts >= CHAT_TIME_GAP_SECONDS:
                    self._chat_view.append(self._chat_time_separator_html(tf))
                prev_msg_ts = tf
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user":
                self._chat_view.append(
                    self._user_row_html(user_u, substitute_bracket_emoticons(content))
                )
            elif role == "sticker":
                html = self._sticker_bubble_html(str(content), peer_u)
                if html:
                    self._chat_view.append(html)
            elif role == "assistant":
                self._chat_view.append(
                    self._assistant_row_html(peer_u, assistant_plain_for_display(content))
                )
        sb = self._chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _add_colleague(self) -> None:
        root = self._settings.skill_root_path.strip()
        if not root:
            QMessageBox.information(self, "新建同事", "请先在设置中填写 Skill 存放路径。")
            return
        root_path = Path(root)
        if not root_path.is_dir():
            QMessageBox.warning(self, "新建同事", "Skill 存放路径不存在或不是目录。")
            return

        desktop = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        start_dir = desktop if desktop else str(root_path)
        picked = QFileDialog.getExistingDirectory(
            self, "选择包含 SKILL.md 的同事目录", start_dir
        )
        if not picked:
            return
        src = Path(picked).resolve()
        skill_file = src / "SKILL.md"
        if not skill_file.is_file():
            QMessageBox.warning(self, "新建同事", "所选目录下未找到 SKILL.md。")
            return

        meta = load_meta(src)
        raw = meta.get("name")
        if isinstance(raw, str) and raw.strip():
            default_name = raw.strip()[:8]
        else:
            default_name = (src.name or "同事")[:8]

        dlg = ImportColleagueNameDialog(default_name, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        display_name = dlg.display_name()

        dest = root_path / src.name

        if src.resolve() == dest.resolve():
            try:
                save_skill_display_name(src, display_name)
            except OSError as e:
                QMessageBox.critical(self, "新建同事", f"保存名称失败：{e}")
                return
            self._unhide_colleague_for_skill_dir(src)
            self._system_cache.clear()
            self._refresh_colleagues()
            self._select_colleague_by_id(self._find_id_for_path(dest))
            return

        if dest.exists():
            r = QMessageBox.question(
                self,
                "新建同事",
                f"目标已存在：{dest}\n是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
            if dest.is_dir():
                shutil.rmtree(dest)

        try:
            shutil.copytree(src, dest)
        except OSError as e:
            QMessageBox.critical(self, "新建同事", f"复制失败：{e}")
            return

        try:
            save_skill_display_name(dest, display_name)
        except OSError as e:
            QMessageBox.critical(self, "新建同事", f"已复制，但保存名称失败：{e}")
            self._system_cache.clear()
            self._refresh_colleagues()
            return

        self._unhide_colleague_for_skill_dir(dest)
        self._system_cache.clear()
        self._refresh_colleagues()
        self._select_colleague_by_id(self._find_id_for_path(dest))

    def _find_id_for_path(self, path: Path) -> str | None:
        path = path.resolve()
        for c in self._colleagues:
            if c.skill_path.resolve() == path:
                return c.colleague_id
        return None

    def _select_colleague_by_id(self, cid: str | None) -> None:
        if not cid:
            return
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == cid:
                self._list.setCurrentItem(item)
                return

    def _send_message(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        c = self._get_current_colleague()
        if not c:
            QMessageBox.information(self, "发送", "请先选择一位同事。")
            return
        if not self._settings.api_key.strip():
            QMessageBox.warning(self, "发送", "请先在设置中填写 API 密钥。")
            return

        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "发送", "请等待当前回复完成。")
            return

        self._input.clear()
        hist = self._histories.setdefault(c.colleague_id, [])
        hist.append(
            {
                "role": "user",
                "content": substitute_bracket_emoticons(text),
                "ts": time.time(),
            }
        )
        self._persist_chat_histories()
        self._render_history()
        # 先插入带头像的一行，占位符处流式写入正文（首包到达前即可看到头像）
        self._stream_insert_cursor = None
        self._stream_plain_start = None
        self._stream_plain_end = None
        peer_u = _chat_avatar_data_url(resolve_colleague_icon(c.skill_path))
        self._chat_view.append(self._assistant_row_html(peer_u, _STREAM_BODY_PLACEHOLDER))
        self._stream_insert_cursor = self._prepare_stream_insert_cursor(_STREAM_BODY_PLACEHOLDER)

        self._streaming_buffer = ""
        self._suppress_stream_chunks = False
        try:
            system = self._system_prompt_for(c)
        except Exception as e:
            self._stream_insert_cursor = None
            self._stream_plain_start = None
            self._stream_plain_end = None
            QMessageBox.critical(self, "Skill", f"加载失败：{e}")
            if hist and hist[-1].get("role") == "user":
                hist.pop()
                self._persist_chat_histories()
            self._render_history()
            return

        self._worker = StreamWorker(
            api_base=self._settings.api_base,
            api_key=self._settings.api_key,
            model=self._settings.model,
            system=system,
            history=hist,
            web_search_enabled=self._web_search_toggle.isChecked(),
            web_search_url=self._settings.ollama_web_search_url,
            web_search_api_key=self._settings.ollama_web_search_api_key,
            parent=self,
        )
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.failed.connect(self._on_stream_failed)
        self._worker.finished_ok.connect(self._on_stream_finished)
        self._worker.status_changed.connect(self._on_stream_remote_status)
        self._streaming_colleague_id = c.colleague_id
        self._worker.start()
        self._stop_stream_btn.setEnabled(True)
        self._begin_stream_loading()

    def _stop_streaming(self) -> None:
        """仅在流式请求进行中有效：打断远端生成，已输出的正文保留。"""
        if not self._worker or not self._worker.isRunning():
            return
        self._suppress_stream_chunks = True
        self._worker.abort()
        # 立刻更新界面：停转圈、禁用终止；无正文时重绘去掉空白气泡，不等待线程退出
        self._cancel_stream_loading_only()
        self._stop_stream_btn.setEnabled(False)
        if not (self._streaming_buffer or "").strip():
            self._stream_insert_cursor = None
            self._stream_plain_start = None
            self._stream_plain_end = None
            if self._streaming_colleague_id == self._current_id:
                self._render_history()

    def _reset_current_session(self) -> None:
        """清空当前同事对话历史与本 Skill 的 system 缓存，相当于新会话。"""
        c = self._get_current_colleague()
        if not c:
            return
        self._histories[c.colleague_id] = []
        self._hist_session_boundary[c.colleague_id] = 0
        self._system_cache.pop(str(c.skill_path), None)
        self._persist_chat_histories()
        self._render_history()

    def _on_refresh_session_clicked(self) -> None:
        """新会话：无流式时直接清空；流式中先打断再清空（不保留半截回复）。"""
        c = self._get_current_colleague()
        if not c:
            QMessageBox.information(self, "新会话", "请先选择一位同事。")
            return
        if self._worker and self._worker.isRunning():
            self._pending_session_reset = True
            self._worker.abort()
            return
        self._reset_current_session()

    def _begin_stream_loading(self, *, preserve_status_message: bool = False) -> None:
        """在首包到达前显示旋转符号和浅灰状态文案（与头像同一行）；文案随后台阶段实时更新。"""
        cur = self._stream_insert_cursor
        if cur is None or cur.isNull():
            return
        anchor = cur.position()
        if not preserve_status_message:
            self._stream_loading_status_message = _STREAM_LOADING_DEFAULT_STATUS
        self._stream_loading_frame = 0
        text = self._stream_loading_display_text()
        self._apply_stream_loading_char_format(cur)
        cur.insertText(text)
        self._stream_loading_anchor = anchor
        self._stream_loading_text = text
        t = QTimer(self)
        t.setInterval(_STREAM_SPINNER_INTERVAL_MS)
        t.timeout.connect(self._tick_stream_loading)
        self._stream_loading_timer = t
        t.start()

    def _update_stream_loading_line(self, *, advance_spinner: bool) -> None:
        """重绘首包前占位行：advance_spinner=True 时仅推进转圈字符。"""
        if (
            self._streaming_colleague_id is None
            or self._streaming_colleague_id != self._current_id
        ):
            return
        if self._stream_loading_anchor is None:
            return
        doc = self._chat_view.document()
        a = self._stream_loading_anchor
        c = QTextCursor(doc)
        c.setPosition(a)
        c.setPosition(a + len(self._stream_loading_text), QTextCursor.MoveMode.KeepAnchor)
        c.removeSelectedText()
        if advance_spinner:
            self._stream_loading_frame += 1
        text = self._stream_loading_display_text()
        self._apply_stream_loading_char_format(c)
        c.insertText(text)
        self._stream_loading_text = text

    def _tick_stream_loading(self) -> None:
        if (
            self._streaming_colleague_id is None
            or self._streaming_colleague_id != self._current_id
        ):
            return
        self._update_stream_loading_line(advance_spinner=True)

    def _take_cursor_after_stream_loading(self) -> QTextCursor | None:
        """首包到达：停表、删掉旋转符，返回用于写入正文的 cursor。"""
        if self._stream_loading_timer is not None:
            self._stream_loading_timer.stop()
            self._stream_loading_timer.deleteLater()
            self._stream_loading_timer = None
        doc = self._chat_view.document()
        out = QTextCursor(doc)
        if self._stream_loading_anchor is not None:
            a = self._stream_loading_anchor
            self._stream_loading_anchor = None
            out.setPosition(a)
            out.setPosition(a + len(self._stream_loading_text), QTextCursor.MoveMode.KeepAnchor)
            out.removeSelectedText()
            out.setPosition(a)
            self._stream_loading_text = ""
            return out
        self._stream_loading_text = ""
        return self._stream_insert_cursor

    def _cancel_stream_loading_only(self) -> None:
        """错误结束 / 关闭窗口：停表并去掉旋转符（若还在）。"""
        if self._stream_loading_timer is not None:
            self._stream_loading_timer.stop()
            self._stream_loading_timer.deleteLater()
            self._stream_loading_timer = None
        if self._stream_loading_anchor is not None:
            doc = self._chat_view.document()
            a = self._stream_loading_anchor
            self._stream_loading_anchor = None
            c = QTextCursor(doc)
            c.setPosition(a)
            c.setPosition(a + len(self._stream_loading_text), QTextCursor.MoveMode.KeepAnchor)
            c.removeSelectedText()
        self._stream_loading_text = ""

    def _prepare_stream_insert_cursor(self, placeholder: str) -> QTextCursor | None:
        doc = self._chat_view.document()
        found = doc.find(placeholder, QTextCursor(doc))
        if found.isNull():
            return None
        found.removeSelectedText()
        return found

    def _on_chunk(self, s: str) -> None:
        if self._suppress_stream_chunks:
            return
        self._streaming_buffer += s
        if self._streaming_colleague_id != self._current_id:
            return
        if self._stream_loading_timer is not None or self._stream_loading_anchor is not None:
            self._stream_insert_cursor = self._take_cursor_after_stream_loading()
        plain = assistant_plain_for_display(self._streaming_buffer)
        doc = self._chat_view.document()
        cur = self._stream_insert_cursor
        if cur is None or cur.isNull():
            c2 = QTextCursor(doc)
            c2.movePosition(QTextCursor.MoveOperation.End)
            self._stream_insert_cursor = c2
            cur = c2
        if self._stream_plain_start is None:
            self._stream_plain_start = cur.position()
            self._stream_plain_end = cur.position()
        c = QTextCursor(doc)
        c.setPosition(self._stream_plain_start)
        c.setPosition(self._stream_plain_end, QTextCursor.MoveMode.KeepAnchor)
        c.removeSelectedText()
        self._apply_stream_text_char_format(c)
        c.insertText(plain)
        self._stream_plain_end = c.position()
        self._stream_insert_cursor = c
        sb = self._chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_stream_failed(self, err: str, exc: object) -> None:
        self._suppress_stream_chunks = False
        stream_cid = self._streaming_colleague_id
        self._streaming_colleague_id = None
        if self._pending_session_reset:
            self._cancel_stream_loading_only()
            self._stream_insert_cursor = None
            self._stream_plain_start = None
            self._stream_plain_end = None
            self._worker = None
            self._streaming_buffer = ""
            self._stop_stream_btn.setEnabled(False)
            self._pending_session_reset = False
            self._reset_current_session()
            return
        self._cancel_stream_loading_only()
        self._stream_insert_cursor = None
        self._stream_plain_start = None
        self._stream_plain_end = None
        self._worker = None
        self._streaming_buffer = ""
        self._stop_stream_btn.setEnabled(False)
        c_stream = self._colleague_by_id(stream_cid)
        if stream_cid and c_stream and _should_show_network_failure_peer_message(exc):
            hist = self._histories.setdefault(stream_cid, [])
            hist.append(
                {
                    "role": "assistant",
                    "content": _NETWORK_FAILURE_PEER_MESSAGE,
                    "ts": time.time(),
                }
            )
            self._persist_chat_histories()
            if self._current_id == stream_cid:
                self._render_history()
            return
        if stream_cid and c_stream and _should_show_api_failure_peer_message(exc):
            hist = self._histories.setdefault(stream_cid, [])
            hist.append(
                {
                    "role": "assistant",
                    "content": _API_FAILURE_PEER_MESSAGE,
                    "ts": time.time(),
                }
            )
            self._persist_chat_histories()
            if self._current_id == stream_cid:
                self._render_history()
            return
        if stream_cid:
            hist = self._histories.get(stream_cid, [])
            if hist and hist[-1].get("role") == "user":
                hist.pop()
                self._persist_chat_histories()
        if self._current_id == stream_cid:
            self._render_history()
            self._chat_view.append(f"<span style='color:red'>[错误] {_escape_html(err)}</span>")

    def _on_stream_finished(self) -> None:
        # 无正文 chunk 时也要去掉等待动画
        self._cancel_stream_loading_only()
        self._stream_insert_cursor = None
        self._stream_plain_start = None
        self._stream_plain_end = None
        w = self._worker
        user_aborted = bool(w and w.user_aborted)
        pending_reset = self._pending_session_reset
        stream_cid = self._streaming_colleague_id
        self._streaming_colleague_id = None
        self._worker = None
        self._suppress_stream_chunks = False
        self._stop_stream_btn.setEnabled(False)
        buf = self._streaming_buffer
        self._streaming_buffer = ""

        if pending_reset:
            self._pending_session_reset = False
            self._reset_current_session()
            return

        if user_aborted:
            # 用户打断：未收到任何正文则不写入助手消息，重绘去掉空白气泡；有部分则只保留已输出
            if not buf.strip():
                if self._current_id == stream_cid:
                    self._render_history()
                return
            if stream_cid:
                hist = self._histories.setdefault(stream_cid, [])
                hist.append(
                    {
                        "role": "assistant",
                        "content": assistant_plain_for_display(buf),
                        "ts": time.time(),
                    },
                )
                self._persist_chat_histories()
            if self._current_id == stream_cid:
                self._render_history()
            return

        if stream_cid and buf:
            hist = self._histories.setdefault(stream_cid, [])
            now = time.time()
            hist.append(
                {
                    "role": "assistant",
                    "content": assistant_plain_for_display(buf),
                    "ts": now,
                }
            )
            if random.random() < STICKER_ROLL_PROB:
                sp = _pick_random_sticker_path()
                if sp is not None:
                    hist.append({"role": "sticker", "content": str(sp), "ts": now})
            self._persist_chat_histories()
        if self._current_id == stream_cid:
            self._render_history()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._cancel_stream_loading_only()
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self._worker.wait(3000)
        self._persist_chat_histories()
        super().closeEvent(event)


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )


def _format_chat_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y年%m月%d日 %H:%M")


def _should_show_api_failure_peer_message(exc: object) -> bool:
    """
    仅在「典型配置/鉴权问题」时用同事口吻，不把网络抖动、限流、服务端 5xx 等误当成「你没配好 API」。
    对话请求会先尝试流式，失败再自动回退非流式（与设置里绿灯测试一致），减少误伤。
    """
    if exc is None:
        return False
    try:
        from openai import (
            AuthenticationError,
            BadRequestError,
            PermissionDeniedError,
        )

        if isinstance(
            exc,
            (
                AuthenticationError,
                PermissionDeniedError,
                BadRequestError,
            ),
        ):
            return True
    except ImportError:
        pass
    return False


def _should_show_network_failure_peer_message(exc: object) -> bool:
    if exc is None:
        return False
    try:
        from openai import APIConnectionError, APITimeoutError

        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return True
    except ImportError:
        pass
    try:
        import httpx

        if isinstance(
            exc,
            (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.ReadError,
                httpx.ReadTimeout,
                httpx.TimeoutException,
            ),
        ):
            return True
    except ImportError:
        pass
    return False
