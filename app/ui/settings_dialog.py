"""设置：左侧分栏 — 基础 / API / 联网 / Skill 路径。"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.api_test import test_api_connection
from app.ollama_web_search import test_web_search_connection
from app.paths import config_dir, user_icon_path
from app.settings import (
    AppSettings,
    DEFAULT_API_BASE,
    DEFAULT_CHAT_FONT_SIZE,
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_WEB_SEARCH_URL,
)


def _api_config_hash(api_base: str, api_key: str, model: str) -> str:
    base = (api_base or "").strip().rstrip("/")
    key = (api_key or "").strip()
    m = (model or "").strip() or DEFAULT_MODEL
    return hashlib.sha256(f"{base}\n{key}\n{m}".encode("utf-8")).hexdigest()


def _web_config_hash(url: str, api_key: str) -> str:
    u = (url or "").strip().rstrip("/")
    key = (api_key or "").strip()
    return hashlib.sha256(f"{u}\n{key}".encode("utf-8")).hexdigest()


_PREVIEW_SIZE = 192

# API / 联网「测试」状态灯：立体圆灯边长（像素）
_STATUS_LAMP_PX = 15

# 与主窗口发送键同款渐变按钮，统一用此 objectName（不加粗）
_SETTINGS_ACTION_BTN_NAME = "SettingsActionBtn"


def _style_settings_action_button(btn: QPushButton) -> None:
    btn.setObjectName(_SETTINGS_ACTION_BTN_NAME)


def _apply_settings_form_layout(form: QFormLayout) -> None:
    """左侧标签与右侧控件行纵向居中对齐（默认会贴顶）。"""
    form.setLabelAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    form.setVerticalSpacing(10)
    form.setHorizontalSpacing(10)


def _square_preview_pixmap(path: Path, size: int) -> QPixmap:
    img = QImage(str(path))
    if img.isNull():
        return QPixmap()
    pm = QPixmap.fromImage(img)
    return pm.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )


def _circular_avatar_pixmap(path: Path, diameter: int) -> QPixmap:
    """圆形头像预览（与主窗口侧栏风格一致）。"""
    square = _square_preview_pixmap(path, diameter)
    if square.isNull():
        return QPixmap()
    x = max(0, (square.width() - diameter) // 2)
    y = max(0, (square.height() - diameter) // 2)
    cropped = square.copy(x, y, diameter, diameter)

    out = QPixmap(diameter, diameter)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    path_clip = QPainterPath()
    path_clip.addEllipse(0, 0, diameter, diameter)
    painter.setClipPath(path_clip)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return out


class _ApiTestThread(QThread):
    finished_ok = Signal(bool)

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._api_base = api_base
        self._api_key = api_key
        self._model = model

    def run(self) -> None:
        ok = test_api_connection(self._api_base, self._api_key, self._model)
        self.finished_ok.emit(ok)


class _WebSearchTestThread(QThread):
    finished_ok = Signal(bool)

    def __init__(
        self,
        api_url: str,
        api_key: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._api_url = api_url
        self._api_key = api_key

    def run(self) -> None:
        ok = test_web_search_connection(self._api_url, self._api_key)
        self.finished_ok.emit(ok)


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: AppSettings,
        parent: QWidget | None = None,
        *,
        initial_page: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(680)
        self.setMinimumHeight(460)
        self._settings = settings
        self._pending_avatar_source: Path | None = None
        self._avatar_reset_default = False

        self._nav = QListWidget()
        self._nav.setObjectName("SettingsNavList")
        self._nav.setSpacing(2)
        self._nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for text in ("基础设置", "API 设置", "联网设置", "Skill 存放路径"):
            it = QListWidgetItem(text)
            it.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._nav.addItem(it)
        self._nav.setCurrentRow(max(0, min(3, initial_page)))

        nav_panel = QFrame()
        nav_panel.setObjectName("SettingsNavPanel")
        nav_lay = QVBoxLayout(nav_panel)
        nav_lay.setContentsMargins(10, 14, 10, 14)
        nav_lay.setSpacing(0)
        nav_lay.addWidget(self._nav)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_page_basic())
        self._stack.addWidget(self._build_page_api())
        self._stack.addWidget(self._build_page_web())
        self._stack.addWidget(self._build_page_skill())

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        for std in (
            QDialogButtonBox.StandardButton.Save,
            QDialogButtonBox.StandardButton.Cancel,
        ):
            b = buttons.button(std)
            if b is not None:
                _style_settings_action_button(b)

        version_lbl = QLabel(f"版本 {__version__}")
        version_lbl.setObjectName("SettingsVersionLabel")
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_lbl.setStyleSheet("color: #9ca3af; font-size: 11px; background: transparent;")

        center = QHBoxLayout()
        center.setSpacing(0)
        center.addWidget(nav_panel)
        center.addWidget(self._stack, stretch=1)

        root = QVBoxLayout(self)
        # 底部留白：按钮下方留空，与窗口底边隔开
        root.setContentsMargins(12, 0, 12, 10)
        root.setSpacing(0)
        root.addLayout(center)
        root.addWidget(version_lbl)
        root.addWidget(buttons)

        self.setStyleSheet(
            """
            QDialog { background: #ffffff; }
            /* 各页「会话字体」「API 地址」「检索 API 地址」等左侧标题：11pt */
            QWidget#SettingsFormPage QLabel {
                font-size: 11pt;
                color: #1a1a1a;
            }
            QWidget#SettingsFormPage QLabel#SettingsStatusLamp {
                font-size: 1px;
                color: transparent;
            }
            QWidget#SettingsFormPage QLabel#SettingsHintLabel {
                font-size: 12px;
                color: #6b7280;
            }
            QFrame#SettingsNavPanel {
                background-color: #ffffff;
                border: none;
                border-right: 1px solid #eeeeee;
                min-width: 168px;
                max-width: 200px;
            }
            QListWidget#SettingsNavList {
                border: none;
                background: transparent;
                outline: none;
                padding: 4px 0;
                font-size: 14px;
            }
            QListWidget#SettingsNavList::item {
                color: #000000;
                padding: 11px 16px;
                margin: 4px 2px;
                border-radius: 10px;
            }
            QListWidget#SettingsNavList::item:selected {
                background: #e8eef5;
                color: #000000;
            }
            QListWidget#SettingsNavList::item:hover {
                background: #f3f4f6;
            }
            QListWidget#SettingsNavList QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 10px;
                margin: 6px 4px 6px 0;
            }
            QListWidget#SettingsNavList QScrollBar::handle:vertical {
                background: #d1d5db;
                border-radius: 5px;
                min-height: 36px;
            }
            QListWidget#SettingsNavList QScrollBar::handle:vertical:hover {
                background: #9ca3af;
            }
            QListWidget#SettingsNavList QScrollBar::add-line:vertical,
            QListWidget#SettingsNavList QScrollBar::sub-line:vertical {
                border: none; background: none; height: 0;
            }
            /* 与主窗口发送键一致的蓝灰渐变；字重常规（不加粗） */
            QPushButton#SettingsActionBtn {
                color: white;
                font-size: 14px;
                font-weight: normal;
                min-width: 80px;
                min-height: 36px;
                max-height: 36px;
                border-radius: 8px;
                padding: 0px 12px;
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #556f95, stop:1 #415a7d);
            }
            QPushButton#SettingsActionBtn:hover {
                border-radius: 8px;
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5f7899, stop:1 #4a6288);
            }
            QPushButton#SettingsActionBtn:pressed {
                border-radius: 8px;
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d5065, stop:1 #4c6a92);
            }
            QDialogButtonBox { background: transparent; }
            """
        )

        self._refresh_avatar_preview()
        self._refresh_lamp()
        self._refresh_web_lamp()

        self.resize(820, 480)

    def _build_page_basic(self) -> QWidget:
        page = QWidget()
        page.setObjectName("SettingsFormPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 24, 20)

        self._avatar_preview = QLabel()
        self._avatar_preview.setFixedSize(_PREVIEW_SIZE, _PREVIEW_SIZE)
        self._avatar_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_preview.setStyleSheet("background: #f3f4f6; border: none;")

        pick = QPushButton("选择图片…")
        _style_settings_action_button(pick)
        pick.clicked.connect(self._pick_avatar)
        reset = QPushButton("恢复默认")
        _style_settings_action_button(reset)
        reset.setToolTip("使用内置默认头像")
        reset.clicked.connect(self._reset_avatar_default)

        row_btn = QHBoxLayout()
        row_btn.addWidget(pick)
        row_btn.addWidget(reset)
        row_btn.addStretch(1)

        hint = QLabel("支持 PNG、JPG / JPEG。更改在点击「保存」后生效。")
        hint.setObjectName("SettingsHintLabel")

        self._font_spin = QSpinBox()
        self._font_spin.setRange(9, 22)
        self._font_spin.setSuffix(" pt")
        self._font_spin.setValue(
            getattr(self._settings, "chat_font_size", DEFAULT_CHAT_FONT_SIZE) or DEFAULT_CHAT_FONT_SIZE
        )
        self._font_spin.setToolTip("会话消息区与输入框的字体大小")

        form = QFormLayout()
        _apply_settings_form_layout(form)
        form.addRow(self._avatar_preview)
        form.addRow(row_btn)
        form.addRow(hint)
        form.addRow("会话字体", self._font_spin)

        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_page_api(self) -> QWidget:
        page = QWidget()
        page.setObjectName("SettingsFormPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 24, 20)

        self._api_base = QLineEdit(self._settings.api_base or DEFAULT_API_BASE)
        self._api_key = QLineEdit(self._settings.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._model = QLineEdit(self._settings.model or DEFAULT_MODEL)

        api_test_row = QWidget()
        api_test_layout = QHBoxLayout(api_test_row)
        api_test_layout.setContentsMargins(0, 0, 0, 0)
        self._lamp = QLabel()
        self._lamp.setObjectName("SettingsStatusLamp")
        self._lamp.setFixedSize(_STATUS_LAMP_PX, _STATUS_LAMP_PX)
        self._lamp.setToolTip(
            "API 连通状态（后台会发一条「hi」对话并检查是否有回复）："
            "灰=未配置或未验证，绿=对话成功，红=失败"
        )
        self._test_btn = QPushButton("测试")
        _style_settings_action_button(self._test_btn)
        self._test_btn.clicked.connect(self._on_test_clicked)
        api_test_layout.addWidget(self._lamp)
        api_test_layout.addStretch()
        api_test_layout.addWidget(self._test_btn)

        self._api_base.textChanged.connect(self._refresh_lamp)
        self._api_key.textChanged.connect(self._refresh_lamp)
        self._model.textChanged.connect(self._refresh_lamp)

        form = QFormLayout()
        _apply_settings_form_layout(form)
        form.addRow("API 地址", self._api_base)
        form.addRow("API 密钥", self._api_key)
        form.addRow("模型名称", self._model)
        form.addRow("API 测试", api_test_row)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_page_web(self) -> QWidget:
        page = QWidget()
        page.setObjectName("SettingsFormPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 24, 20)

        self._web_url = QLineEdit(
            (self._settings.ollama_web_search_url or DEFAULT_OLLAMA_WEB_SEARCH_URL).strip()
            or DEFAULT_OLLAMA_WEB_SEARCH_URL
        )
        self._web_url.setPlaceholderText(DEFAULT_OLLAMA_WEB_SEARCH_URL)
        self._web_key = QLineEdit(self._settings.ollama_web_search_api_key)
        self._web_key.setEchoMode(QLineEdit.EchoMode.Password)

        web_test_row = QWidget()
        web_test_layout = QHBoxLayout(web_test_row)
        web_test_layout.setContentsMargins(0, 0, 0, 0)
        self._web_lamp = QLabel()
        self._web_lamp.setObjectName("SettingsStatusLamp")
        self._web_lamp.setFixedSize(_STATUS_LAMP_PX, _STATUS_LAMP_PX)
        self._web_lamp.setToolTip(
            "联网检索连通状态：灰=未验证或配置已改，绿=测试成功，红=失败"
        )
        self._web_test_btn = QPushButton("测试")
        _style_settings_action_button(self._web_test_btn)
        self._web_test_btn.clicked.connect(self._on_web_test_clicked)
        web_test_layout.addWidget(self._web_lamp)
        web_test_layout.addStretch()
        web_test_layout.addWidget(self._web_test_btn)

        self._web_url.textChanged.connect(self._refresh_web_lamp)
        self._web_key.textChanged.connect(self._refresh_web_lamp)

        form = QFormLayout()
        _apply_settings_form_layout(form)
        form.addRow("检索 API 地址", self._web_url)
        form.addRow("检索 API 密钥", self._web_key)
        form.addRow("联网测试", web_test_row)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_page_skill(self) -> QWidget:
        page = QWidget()
        page.setObjectName("SettingsFormPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 24, 20)

        skill_row = QWidget()
        skill_layout = QHBoxLayout(skill_row)
        skill_layout.setContentsMargins(0, 0, 0, 0)
        self._skill_root = QLineEdit(self._settings.skill_root_path)
        self._skill_root.setPlaceholderText("用于「新建同事」时复制 skill 目录到此路径下")
        browse = QPushButton("浏览…")
        _style_settings_action_button(browse)
        browse.clicked.connect(self._browse_skill_root)
        skill_layout.addWidget(self._skill_root)
        skill_layout.addWidget(browse)

        form = QFormLayout()
        _apply_settings_form_layout(form)
        form.addRow("Skill 存放路径", skill_row)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _preview_path_for_display(self) -> Path:
        if self._avatar_reset_default:
            return user_icon_path(AppSettings())
        if self._pending_avatar_source is not None:
            return self._pending_avatar_source
        return user_icon_path(self._settings)

    def _refresh_avatar_preview(self) -> None:
        path = self._preview_path_for_display()
        pm = _circular_avatar_pixmap(path, _PREVIEW_SIZE)
        if pm.isNull():
            self._avatar_preview.clear()
            self._avatar_preview.setText("无预览")
            return
        self._avatar_preview.setPixmap(pm)

    def _pick_avatar(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "选择头像",
            "",
            "图片 (*.png *.jpg *.jpeg);;PNG (*.png);;JPEG (*.jpg *.jpeg)",
        )
        if not path_str:
            return
        p = Path(path_str)
        suf = p.suffix.lower()
        if suf not in (".png", ".jpg", ".jpeg"):
            QMessageBox.warning(self, "头像", "请选择 PNG 或 JPG / JPEG 图片。")
            return
        self._pending_avatar_source = p
        self._avatar_reset_default = False
        self._refresh_avatar_preview()

    def _reset_avatar_default(self) -> None:
        self._pending_avatar_source = None
        self._avatar_reset_default = True
        self._refresh_avatar_preview()

    def _set_lamp_color(self, lamp: QLabel, state: str) -> None:
        """
        立体圆灯：径向渐变模拟 LED 高光；无边框。
        动态样式挂在控件上，覆盖全局 QLabel 字号规则。
        """
        r = _STATUS_LAMP_PX // 2
        if state == "green":
            style = f"""
                QLabel#SettingsStatusLamp {{
                    min-width: {_STATUS_LAMP_PX}px;
                    max-width: {_STATUS_LAMP_PX}px;
                    min-height: {_STATUS_LAMP_PX}px;
                    max-height: {_STATUS_LAMP_PX}px;
                    border-radius: {r}px;
                    border: none;
                    background: qradialgradient(
                        spread:pad, cx:0.38, cy:0.32, radius:0.92, fx:0.32, fy:0.28,
                        stop:0 #e8f8ea,
                        stop:0.25 #7fdc85,
                        stop:0.55 #2fa036,
                        stop:0.82 #1e6b22,
                        stop:1 #123d16
                    );
                }}
            """
        elif state == "red":
            style = f"""
                QLabel#SettingsStatusLamp {{
                    min-width: {_STATUS_LAMP_PX}px;
                    max-width: {_STATUS_LAMP_PX}px;
                    min-height: {_STATUS_LAMP_PX}px;
                    max-height: {_STATUS_LAMP_PX}px;
                    border-radius: {r}px;
                    border: none;
                    background: qradialgradient(
                        spread:pad, cx:0.38, cy:0.32, radius:0.92, fx:0.32, fy:0.28,
                        stop:0 #fff0f0,
                        stop:0.25 #ff8a80,
                        stop:0.55 #e53935,
                        stop:0.82 #b71c1c,
                        stop:1 #5c1010
                    );
                }}
            """
        else:
            style = f"""
                QLabel#SettingsStatusLamp {{
                    min-width: {_STATUS_LAMP_PX}px;
                    max-width: {_STATUS_LAMP_PX}px;
                    min-height: {_STATUS_LAMP_PX}px;
                    max-height: {_STATUS_LAMP_PX}px;
                    border-radius: {r}px;
                    border: none;
                    background: qradialgradient(
                        spread:pad, cx:0.38, cy:0.32, radius:0.92, fx:0.32, fy:0.28,
                        stop:0 #ffffff,
                        stop:0.3 #d1d5db,
                        stop:0.6 #9ca3af,
                        stop:0.85 #6b7280,
                        stop:1 #3d4450
                    );
                }}
            """
        lamp.setStyleSheet(style)

    def _refresh_lamp(self) -> None:
        base = self._api_base.text().strip()
        key = self._api_key.text().strip()
        model = self._model.text().strip() or DEFAULT_MODEL
        if not key:
            self._set_lamp_color(self._lamp, "gray")
            return
        h = _api_config_hash(base, key, model)
        if h != (self._settings.api_last_test_hash or ""):
            self._set_lamp_color(self._lamp, "gray")
            return
        ok = self._settings.api_last_test_ok
        if ok is True:
            self._set_lamp_color(self._lamp, "green")
        elif ok is False:
            self._set_lamp_color(self._lamp, "red")
        else:
            self._set_lamp_color(self._lamp, "gray")

    def _refresh_web_lamp(self) -> None:
        url = self._web_url.text().strip() or DEFAULT_OLLAMA_WEB_SEARCH_URL
        key = self._web_key.text().strip()
        if not key:
            self._set_lamp_color(self._web_lamp, "gray")
            return
        h = _web_config_hash(url, key)
        if h != (self._settings.web_last_test_hash or ""):
            self._set_lamp_color(self._web_lamp, "gray")
            return
        ok = self._settings.web_last_test_ok
        if ok is True:
            self._set_lamp_color(self._web_lamp, "green")
        elif ok is False:
            self._set_lamp_color(self._web_lamp, "red")
        else:
            self._set_lamp_color(self._web_lamp, "gray")

    def _browse_skill_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 Skill 根目录", self._skill_root.text() or "")
        if path:
            self._skill_root.setText(path)

    def _apply_test_result(self, ok: bool, api_base: str, api_key: str, model: str) -> None:
        h = _api_config_hash(api_base, api_key, model)
        self._settings.api_last_test_ok = ok
        self._settings.api_last_test_hash = h
        self._settings.save()
        self._refresh_lamp()

    def _apply_web_test_result(self, ok: bool, url: str, key: str) -> None:
        h = _web_config_hash(url, key)
        self._settings.web_last_test_ok = ok
        self._settings.web_last_test_hash = h
        self._settings.save()
        self._refresh_web_lamp()

    def _on_test_clicked(self) -> None:
        base = self._api_base.text().strip()
        if not base:
            QMessageBox.warning(self, "设置", "请填写 API 地址。")
            return
        key = self._api_key.text().strip()
        if not key:
            QMessageBox.warning(self, "设置", "请填写 API 密钥。")
            return
        model = self._model.text().strip() or DEFAULT_MODEL
        self._test_btn.setEnabled(False)
        self._thread = _ApiTestThread(base, key, model, self)
        self._thread.finished_ok.connect(self._on_manual_test_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_manual_test_finished(self, ok: bool) -> None:
        self._test_btn.setEnabled(True)
        base = self._api_base.text().strip()
        key = self._api_key.text().strip()
        model = self._model.text().strip() or DEFAULT_MODEL
        self._apply_test_result(ok, base, key, model)

    def _on_web_test_clicked(self) -> None:
        url = self._web_url.text().strip() or DEFAULT_OLLAMA_WEB_SEARCH_URL
        key = self._web_key.text().strip()
        if not key:
            QMessageBox.warning(self, "设置", "请填写检索 API 密钥。")
            return
        self._web_test_btn.setEnabled(False)
        self._web_thread = _WebSearchTestThread(url, key, self)
        self._web_thread.finished_ok.connect(self._on_web_manual_test_finished)
        self._web_thread.finished.connect(self._web_thread.deleteLater)
        self._web_thread.start()

    def _on_web_manual_test_finished(self, ok: bool) -> None:
        self._web_test_btn.setEnabled(True)
        url = self._web_url.text().strip() or DEFAULT_OLLAMA_WEB_SEARCH_URL
        key = self._web_key.text().strip()
        self._apply_web_test_result(ok, url, key)

    def _accept(self) -> None:
        base = self._api_base.text().strip()
        if not base:
            QMessageBox.warning(self, "设置", "请填写 API 地址。")
            return

        # 头像：保存时写入
        if self._avatar_reset_default:
            self._settings.user_avatar_path = ""
            dest = config_dir() / "user_avatar.png"
            if dest.is_file():
                try:
                    dest.unlink()
                except OSError:
                    pass
        elif self._pending_avatar_source is not None:
            img = QImage(str(self._pending_avatar_source))
            if img.isNull():
                QMessageBox.warning(self, "头像", "无法读取所选图片。")
                return
            dest = config_dir() / "user_avatar.png"
            if not img.save(str(dest), "PNG"):
                QMessageBox.warning(self, "头像", "保存头像失败，请检查磁盘与权限。")
                return
            self._settings.user_avatar_path = str(dest.resolve())

        self._settings.api_base = base
        self._settings.api_key = self._api_key.text().strip()
        self._settings.model = self._model.text().strip() or DEFAULT_MODEL
        self._settings.skill_root_path = self._skill_root.text().strip()

        self._settings.chat_font_size = int(self._font_spin.value())

        web_u = self._web_url.text().strip() or DEFAULT_OLLAMA_WEB_SEARCH_URL
        self._settings.ollama_web_search_url = web_u
        self._settings.ollama_web_search_api_key = self._web_key.text().strip()

        key = self._settings.api_key.strip()
        if not key:
            self._settings.api_last_test_ok = None
            self._settings.api_last_test_hash = ""

        wkey = self._settings.ollama_web_search_api_key.strip()
        if not wkey:
            self._settings.web_last_test_ok = None
            self._settings.web_last_test_hash = ""

        self._settings.save()

        if key:
            model = self._settings.model.strip() or DEFAULT_MODEL
            holder = self.parent() or self
            bg = _ApiTestThread(base, key, model, holder)
            settings_ref = self._settings

            def on_bg_done(ok: bool) -> None:
                settings_ref.api_last_test_ok = ok
                settings_ref.api_last_test_hash = _api_config_hash(base, key, model)
                settings_ref.save()

            bg.finished_ok.connect(on_bg_done)
            bg.finished.connect(bg.deleteLater)
            bg.start()
        self.accept()

