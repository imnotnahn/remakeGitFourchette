# -----------------------------------------------------------------------------
# Copyright (C) 2024 Iliyas Jorio.
# This file is part of GitFourchette, distributed under the GNU GPL v3.
# For full terms, see the included LICENSE file.
# -----------------------------------------------------------------------------

from gitfourchette.forms.brandeddialog import convertToBrandedDialog
from gitfourchette.forms.signatureform import SignatureForm
from gitfourchette.forms.ui_identitydialog import Ui_IdentityDialog
from gitfourchette.localization import *
from gitfourchette.qt import *
from gitfourchette.toolbox import *
import logging


class IdentityDialog(QDialog):
    def __init__(
            self,
            firstRun: bool,
            initialName: str,
            initialEmail: str,
            configPath: str,
            repoHasLocalIdentity: bool,
            parent: QWidget
    ):
        super().__init__(parent)

        ui = Ui_IdentityDialog()
        ui.setupUi(self)
        self.ui = ui

        formatWidgetText(ui.configPathLabel, lquo(compactPath(configPath)))
        ui.warningLabel.setVisible(repoHasLocalIdentity)

        # Initialize with global identity values (if any)
        ui.nameEdit.setText(initialName)
        ui.emailEdit.setText(initialEmail)
        
        # Quick authentication is checked by default
        ui.quickAuthCheckBox.setChecked(True)
        
        # Add PAT (Personal Access Token) fields
        self.setupPATFields()
        
        # Load saved PAT credentials if they exist
        self.loadPATCredentials()

        validator = ValidatorMultiplexer(self)
        validator.setGatedWidgets(ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok))
        validator.connectInput(ui.nameEdit, SignatureForm.validateInput)
        validator.connectInput(ui.emailEdit, SignatureForm.validateInput)
        validator.run(silenceEmptyWarnings=True)

        subtitle = _("This information will be embedded in the commits and tags that you create on this machine.")
        if firstRun:
            subtitle = _("Before editing this repository, please set up your identity for Git.") + " " + subtitle

        convertToBrandedDialog(self, subtitleText=subtitle, multilineSubtitle=True)
    
    def setupPATFields(self):
        # Create a new group box for PAT authentication
        patGroupBox = QGroupBox(_("GitHub/GitLab Authentication"))
        patLayout = QFormLayout(patGroupBox)
        
        # Add username field
        self.patUsernameEdit = QLineEdit()
        patLayout.addRow(_("Username:"), self.patUsernameEdit)
        
        # Add token field
        self.patTokenEdit = QLineEdit()
        self.patTokenEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self.patTokenEdit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        patLayout.addRow(_("Personal Access Token:"), self.patTokenEdit)
        
        # Add explanation text
        infoLabel = QLabel(_("These credentials will be used for remote operations like push/pull. " 
                           "The token will be stored in your git config."))
        infoLabel.setWordWrap(True)
        patLayout.addRow(infoLabel)
        
        # Add toggle visibility button
        self.echoModeAction = self.patTokenEdit.addAction(
            stockIcon("view-visible"), 
            QLineEdit.ActionPosition.TrailingPosition
        )
        self.echoModeAction.setToolTip(_("Reveal token"))
        self.echoModeAction.triggered.connect(self.onToggleEchoMode)
        
        # Add the PAT group to the main layout, before the buttonBox
        mainLayout = self.layout()
        mainLayout.insertWidget(mainLayout.count()-1, patGroupBox)
        
        # Store references
        self.patGroupBox = patGroupBox
    
    def loadPATCredentials(self):
        """Load PAT credentials from git config if they exist"""
        try:
            configObject = GitConfigHelper.ensure_file(GitConfigLevel.GLOBAL)
            
            # Use dictionary style access with try/except instead of get()
            try:
                username = configObject['credential.username']
                if username:
                    self.patUsernameEdit.setText(username)
            except KeyError:
                pass
                
            try:
                token = configObject['credential.pattoken']
                if token:
                    self.patTokenEdit.setText(token)
            except KeyError:
                pass
                
        except Exception as e:
            # Just log and continue if we can't load credentials
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to load PAT credentials: {e}")
    
    def onToggleEchoMode(self):
        """Toggle between showing and hiding the PAT token"""
        passwordMode = self.patTokenEdit.echoMode() == QLineEdit.EchoMode.Password
        passwordMode = not passwordMode
        self.patTokenEdit.setEchoMode(QLineEdit.EchoMode.Password if passwordMode else QLineEdit.EchoMode.Normal)
        self.echoModeAction.setIcon(stockIcon("view-visible" if passwordMode else "view-hidden"))
        self.echoModeAction.setToolTip(_("Reveal token") if passwordMode else _("Hide token"))
        self.echoModeAction.setChecked(not passwordMode)

    def identity(self) -> tuple[str, str]:
        name = self.ui.nameEdit.text()
        email = self.ui.emailEdit.text()
        return name, email
    
    def patCredentials(self) -> tuple[str, str]:
        """Return the PAT credentials (username, token)"""
        username = self.patUsernameEdit.text()
        token = self.patTokenEdit.text()
        return username, token
        
    def isQuickAuthEnabled(self) -> bool:
        return self.ui.quickAuthCheckBox.isChecked()
