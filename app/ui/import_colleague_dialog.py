"""Dialog: set display name when importing a skill (max 8 characters)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


class ImportColleagueNameDialog(QDialog):
    def __init__(
        self,
        default_name: str,
        parent=None,
        *,
        window_title: str = "再生同事",
        prompt: str = "给我起个名呗(最多 8 个字)：",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(window_title)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(prompt))
        self._edit = QLineEdit()
        self._edit.setMaxLength(8)
        self._edit.setText((default_name or "")[:8])
        self._edit.setPlaceholderText("显示在左侧列表的名称")
        layout.addWidget(self._edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._edit.setFocus()
        self._edit.selectAll()

    def _try_accept(self) -> None:
        if not self._edit.text().strip():
            QMessageBox.warning(self, "新建同事", "名称不能为空。")
            return
        self.accept()

    def display_name(self) -> str:
        return self._edit.text().strip()
