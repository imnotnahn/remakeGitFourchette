# -----------------------------------------------------------------------------
# Copyright (C) 2025 Iliyas Jorio.
# This file is part of GitFourchette, distributed under the GNU GPL v3.
# For full terms, see the included LICENSE file.
# -----------------------------------------------------------------------------

from gitfourchette import settings
from gitfourchette.localization import *
from gitfourchette.forms.textinputdialog import TextInputDialog
from gitfourchette.qt import *
from gitfourchette.toolbox import *


class PersonalAccessTokenDialog(TextInputDialog):
    tokenReady = Signal(str, str)

    def __init__(self, parent: QWidget, url: str):
        super().__init__(
            parent,
            _("Personal Access Token (PAT) Authentication"),
            _("Enter your username and Personal Access Token for:"),
            subtitle=escape(url))

        self.url = url
        
        # Create layout for username and token
        extraWidget = QWidget()
        formLayout = QFormLayout(extraWidget)
        formLayout.setContentsMargins(0, 0, 0, 0)
        
        # Username field
        self.usernameEdit = QLineEdit()
        formLayout.addRow(_("Username:"), self.usernameEdit)
        
        # Token field (this replaces the normal line edit)
        self.tokenEdit = QLineEdit()
        self.tokenEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tokenEdit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        formLayout.addRow(_("Token:"), self.tokenEdit)
        
        # Replace the default line edit with our custom widget
        self.setExtraWidget(extraWidget)
        self.lineEdit.hide()  # Hide the original line edit

        # Remember checkbox
        rememberCheckBox = QCheckBox(_("Remember token for this session"))
        rememberCheckBox.setChecked(settings.prefs.rememberPassphrases)
        rememberCheckBox.checkStateChanged.connect(self.onRememberCheckStateChanged)
        formLayout.addRow("", rememberCheckBox)
        self.rememberCheckBox = rememberCheckBox

        # Add show/hide button for token
        self.echoModeAction = self.tokenEdit.addAction(stockIcon("view-visible"), QLineEdit.ActionPosition.TrailingPosition)
        self.echoModeAction.setToolTip(_("Reveal token"))
        self.echoModeAction.triggered.connect(self.onToggleEchoMode)

        self.finished.connect(self.onFinish)
        
        # Focus on username field
        self.usernameEdit.setFocus()

    def onRememberCheckStateChanged(self, state: Qt.CheckState):
        settings.prefs.rememberPassphrases = state == Qt.CheckState.Checked
        settings.prefs.setDirty()

    def onToggleEchoMode(self):
        passwordMode = self.tokenEdit.echoMode() == QLineEdit.EchoMode.Password
        passwordMode = not passwordMode
        self.tokenEdit.setEchoMode(QLineEdit.EchoMode.Password if passwordMode else QLineEdit.EchoMode.Normal)
        self.echoModeAction.setIcon(stockIcon("view-visible" if passwordMode else "view-hidden"))
        self.echoModeAction.setToolTip(_("Reveal token") if passwordMode else _("Hide token"))
        self.echoModeAction.setChecked(not passwordMode)

    def onFinish(self, result):
        if result:
            username = self.usernameEdit.text()
            token = self.tokenEdit.text()
            self.tokenReady.emit(username, token)
        else:
            self.tokenReady.emit("", "") 