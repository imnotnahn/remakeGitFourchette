# -----------------------------------------------------------------------------
# Copyright (C) 2025 Iliyas Jorio.
# This file is part of GitFourchette, distributed under the GNU GPL v3.
# For full terms, see the included LICENSE file.
# -----------------------------------------------------------------------------

from __future__ import annotations

import base64
import logging
import re
from contextlib import suppress
from pathlib import Path

from gitfourchette import settings
from gitfourchette.forms.passphrasedialog import PassphraseDialog
from gitfourchette.forms.pat_dialog import PersonalAccessTokenDialog
from gitfourchette.localization import *
from gitfourchette.porcelain import *
from gitfourchette.qt import *
from gitfourchette.repoprefs import RepoPrefs
from gitfourchette.settings import TEST_MODE
from gitfourchette.toolbox import *

# Import UserPass from pygit2 for PAT authentication
from pygit2 import UserPass

logger = logging.getLogger(__name__)

DLRATE_REFRESH_INTERVAL = 500


def getAuthNamesFromFlags(allowedTypes):
    allowedTypeNames = []
    for credential in CredentialType:
        if allowedTypes & credential:
            allowedTypeNames.append(credential.name.lower())
    return ", ".join(allowedTypeNames)


def isPrivateKeyPassphraseProtected(path: str):
    lines = Path(path).read_text("utf-8").splitlines(keepends=False)

    while lines and not re.match("^-+END OPENSSH PRIVATE KEY-+ *$", lines.pop()):
        continue

    while lines and not re.match("^-+BEGIN OPENSSH PRIVATE KEY-+ *$", lines.pop(0)):
        continue

    if not lines:
        return False

    keyContents = base64.b64decode("".join(lines))

    return b"bcrypt" in keyContents


def collectUserKeyFiles():
    if TEST_MODE:
        from test.util import getTestDataPath
        sshDirectory = getTestDataPath("keys")
    else:  # pragma: no cover
        sshDirectory = QStandardPaths.locate(QStandardPaths.StandardLocation.HomeLocation, ".ssh", QStandardPaths.LocateOption.LocateDirectory)

    keypairFiles: list[tuple[str, str]] = []

    if not sshDirectory:
        return keypairFiles

    for publicKey in Path(sshDirectory).glob("*.pub"):
        privateKey = publicKey.with_suffix("")
        if publicKey.is_file() and privateKey.is_file():
            logger.debug(f"Discovered key pair {privateKey}")
            keypairFiles.append((str(publicKey), str(privateKey)))

    return keypairFiles


class RemoteLink(QObject, RemoteCallbacks):
    sessionPassphrases = {}
    sessionPATCredentials = {}  # Store PAT credentials for this session

    userAbort = Signal()
    message = Signal(str)
    progress = Signal(int, int)
    beginRemote = Signal(str, str)

    # Pass messages between network thread and UI thread for passphrase prompt
    requestPassphrase = Signal(str, object)
    
    # Pass messages for PAT credentials
    requestPAT = Signal(str, object)

    updatedTips: dict[str, tuple[Oid, Oid]]

    @staticmethod
    def mayAbortNetworkOperation(f):
        def wrapper(*args):
            x: RemoteLink = args[0]
            if x._aborting:
                raise InterruptedError(_("Remote operation interrupted by user."))
            return f(*args)
        return wrapper

    @classmethod
    def clearSessionPassphrases(cls):
        cls.sessionPassphrases.clear()
        cls.sessionPATCredentials.clear()

    def __init__(self, parent: QObject):
        QObject.__init__(self, parent)
        RemoteCallbacks.__init__(self)

        assert findParentWidget(self)

        self.setObjectName("RemoteLink")
        self.transferRateTimer = QElapsedTimer()

        self.resetLoginState()
        self._aborting = False
        self._busy = False
        self.updatedTips = {}

        self.userAbort.connect(self._onAbort)
        self.requestPassphrase.connect(self.showPassphraseDialog)
        self.requestPAT.connect(self.showPATDialog)

    def resetLoginState(self):
        self.attempts = 0

        self.keypairFiles = []
        self.usingCustomKeyFile = ""
        self.moreDetailsOnCustomKeyFileFail = True
        self.anyKeyIsUnreadable = False

        self.lastAttemptKey = ""
        self.lastAttemptUrl = ""
        self.lastAttemptPassphrase = None
        self.usingKnownKeyFirst = False  # for informative purposes only

        # PAT authentication state
        self.patAttempted = False
        self.lastAttemptUsername = ""
        self.lastAttemptToken = ""

        self.transferRate = 0
        self.transferredBytesAtTimerStart = 0
        self.transferCompleteAtTimerStart = False
        self.transferRateTimer.invalidate()

        self._sidebandProgressBuffer = ""

    def forceCustomKeyFile(self, privKeyPath):
        self.usingCustomKeyFile = privKeyPath
        self.moreDetailsOnCustomKeyFileFail = False

    def discoverKeyFiles(self, remote: Remote | str = ""):
        # Find remote-specific key files
        if isinstance(remote, Remote) and not self.usingCustomKeyFile:
            assert isinstance(remote._repo, Repo)
            self.usingCustomKeyFile = RepoPrefs.getRemoteKeyFileForRepo(remote._repo, remote.name)

        if self.usingCustomKeyFile:
            privkey = self.usingCustomKeyFile
            pubkey = privkey + ".pub"

            if not Path(pubkey).is_file():
                raise FileNotFoundError(_("Remote-specific public key file not found:") + " " + compactPath(pubkey))

            if not Path(privkey).is_file():
                raise FileNotFoundError(_("Remote-specific private key file not found:") + " " + compactPath(privkey))

            logger.info(f"Using remote-specific key pair {privkey}")

            self.keypairFiles.append((pubkey, privkey))

        # Find user key files
        else:
            self.keypairFiles.extend(collectUserKeyFiles())

            # If we've already connected to this host before,
            # give higher priority to the key that we used last
            if remote:
                url = remote.url if isinstance(remote, Remote) else remote
                assert type(url) is str
                strippedUrl = stripRemoteUrlPath(url)
                if strippedUrl and strippedUrl in settings.history.workingKeys:
                    workingKey = settings.history.workingKeys[strippedUrl]
                    self.keypairFiles.sort(key=lambda tup: tup[1] != workingKey)
                    logger.debug(f"Will try key '{workingKey}' first because it has been used in the past to access '{strippedUrl}'")
                    self.usingKnownKeyFirst = True

        # See if any of the keys are unreadable
        for _pubkey, privkey in self.keypairFiles:
            try:
                # Just some dummy read
                isPrivateKeyPassphraseProtected(privkey)
            except OSError:
                self.anyKeyIsUnreadable = True
                break

    def isAborting(self):
        return self._aborting

    def isBusy(self):
        return self._busy

    def raiseAbortFlag(self):
        self.message.emit(_("Aborting remote operation…"))
        self.progress.emit(0, 0)
        self.userAbort.emit()

    def _onAbort(self):
        self._aborting = True
        logger.info("Abort flag set.")

    @mayAbortNetworkOperation
    def sideband_progress(self, string):
        # The remote sends a stream of characters intended to be printed
        # progressively. So, the string we receive may be incomplete.
        string = self._sidebandProgressBuffer + string

        # \r refreshes the current status line, and \n starts a new one.
        # Send the last complete line we have.
        split = string.replace("\r", "\n").rsplit("\n", 2)
        with suppress(IndexError):
            logger.info(f"[sideband] {split[-2]}")

        # Buffer partial message for next time.
        self._sidebandProgressBuffer = split[-1]

    # def certificate_check(self, certificate, valid, host):
    #     gflog("RemoteLink", "Certificate Check", certificate, valid, host)
    #     return 1

    def handleStoredPATFailure(self, url):
        """Handle the case where stored PAT credentials failed"""
        logger.warning("Stored PAT credentials failed")
        
        # Show a notification to the user
        self.message.emit(_("Stored authentication credentials failed. You will be prompted to enter new credentials."))
        
        # Clear the cached credentials for this URL
        url_key = stripRemoteUrlPath(url)
        if url_key in self.sessionPATCredentials:
            del self.sessionPATCredentials[url_key]
            
        # Mark these credentials as attempted (and failed)
        self.patAttempted = True

    @mayAbortNetworkOperation
    def credentials(self, url, username_from_url, allowed_types):
        self.attempts += 1
        self.lastAttemptKey = ""
        self.lastAttemptPassphrase = None
        self.lastAttemptUrl = url  # Store the URL for future reference

        if self.attempts > 10:
            raise ConnectionRefusedError(_("Too many credential retries."))

        if self.attempts == 1:
            logger.info(f"Auths accepted by server: {getAuthNamesFromFlags(allowed_types)}")
        
        # Try using stored PAT credentials first for USERPASS_PLAINTEXT
        if allowed_types & CredentialType.USERPASS_PLAINTEXT:
            # First check session cache
            url_key = stripRemoteUrlPath(url)
            if url_key in self.sessionPATCredentials:
                logger.info(f"Using cached PAT credentials for {url_key}")
                username, token = self.sessionPATCredentials[url_key]
                return UserPass(username, token)
            
            # If we've already attempted PAT auth and it failed, don't try again with stored credentials
            if self.patAttempted and self.attempts > 1:
                pass
            else:
                # Check git config
                try:
                    # Get global config
                    config = GitConfigHelper.ensure_file(GitConfigLevel.GLOBAL)
                    # Use dictionary-style access with try/except instead of .get()
                    try:
                        username = config['credential.username']
                        token = config['credential.pattoken']
                        
                        if username and token:
                            logger.info(f"Using stored PAT credentials from git config")
                            # Store in session cache for future use
                            self.lastAttemptUsername = username
                            self.lastAttemptToken = token
                            
                            # If this is the second attempt, it means stored credentials failed
                            if self.attempts > 1:
                                self.handleStoredPATFailure(url)
                            else:
                                # First attempt with stored credentials
                                return UserPass(username, token)
                    except KeyError:
                        # Key doesn't exist in config
                        logger.info("No PAT credentials found in git config")
                except Exception as e:
                    logger.warning(f"Failed to retrieve PAT credentials from git config: {e}")

        # Try SSH key authentication
        if self.keypairFiles and (allowed_types & CredentialType.SSH_KEY):
            pubkey, privkey = self.keypairFiles.pop(0)
            logger.info(f"Logging in with: {compactPath(pubkey)}")
            self.message.emit(_("Logging in with key:") + " " + compactPath(pubkey))
            passphrase = self.getPassphraseFromNetworkThread(privkey)
            self.lastAttemptKey = privkey
            self.lastAttemptUrl = url
            self.lastAttemptPassphrase = passphrase
            return Keypair(username_from_url, pubkey, privkey, passphrase)
        
        # Try Personal Access Token (PAT) if SSH authentication fails or is not available
        elif not self.patAttempted and (allowed_types & CredentialType.USERPASS_PLAINTEXT):
            self.patAttempted = True  # Only try PAT once per authentication attempt
            
            # Check if we already have PAT stored for this URL
            strippedUrl = stripRemoteUrlPath(url)
            if strippedUrl in self.sessionPATCredentials:
                stored_username, stored_token = self.sessionPATCredentials[strippedUrl]
                self.lastAttemptUsername = stored_username
                self.lastAttemptToken = stored_token
                return UserPass(stored_username, stored_token)
            
            # Request PAT from user
            self.message.emit(_("Requesting Personal Access Token authentication..."))
            username, token = self.getPATFromNetworkThread(url)
            
            if not username or not token:
                # User canceled PAT authentication
                raise ConnectionRefusedError(_("Authentication canceled by user."))
                
            self.lastAttemptUsername = username
            self.lastAttemptToken = token
            self.lastAttemptUrl = url
            
            return UserPass(username, token)
        
        elif self.attempts == 0:
            raise NotImplementedError(
                _("Unsupported authentication type.") + " " +
                _("The remote claims to accept: {0}.", getAuthNamesFromFlags(allowed_types)))
        elif self.anyKeyIsUnreadable:
            raise ConnectionRefusedError(
                _("Could not find suitable key files for this remote.") + " " +
                _("The key files couldn't be opened (permission issues?)."))
        elif self.usingCustomKeyFile:
            message = _("The remote has rejected your custom key file ({0}).", compactPath(self.usingCustomKeyFile))
            if self.moreDetailsOnCustomKeyFileFail:
                message += " "
                message += _("To change key file settings for this remote, right-click on the remote in the sidebar and pick \"Edit Remote\".")
            raise ConnectionRefusedError(message)
        else:
            raise ConnectionRefusedError(_("Connection refused: Credentials rejected by remote."))
        
        # Return None to tell libgit2 to continue trying other authentication methods
        # If we've exhausted all options, the function won't be called again
        return None

    @mayAbortNetworkOperation
    def transfer_progress(self, stats: TransferProgress):
        self._genericTransferProgress(
            stats.received_objects, stats.total_objects, stats.received_bytes,
            transferingMessage=_("Receiving objects: {prct}% ({obj}/{total}), {rate}/s | {bytes}"),
            completeMessage=_("Received {total} objects in total."),
            showIndexingProgress=True)

    @mayAbortNetworkOperation
    def push_transfer_progress(self, objects_pushed: int, total_objects: int, bytes_pushed: int):
        self._genericTransferProgress(
            objects_pushed, total_objects, bytes_pushed,
            transferingMessage=_("Writing objects: {prct}% ({obj}/{total}), {rate}/s | {bytes}"),
            completeMessage=_("Pushed {total} objects in total."),
            showIndexingProgress=False)

    def _genericTransferProgress(self, objectsTransferred: int, totalObjects: int, bytesTransferred: int,
                             transferingMessage: str, completeMessage: str, showIndexingProgress=True):
        obj = min(objectsTransferred, totalObjects)
        transferComplete = obj == totalObjects

        # Transfer rate
        if not self.transferRateTimer.isValid() or transferComplete != self.transferCompleteAtTimerStart:
            self.transferRateTimer.restart()
            self.transferredBytesAtTimerStart = bytesTransferred
            self.transferCompleteAtTimerStart = transferComplete
            self.transferRate = 0
        elif self.transferRateTimer.hasExpired(DLRATE_REFRESH_INTERVAL):
            elapsedMs = max(1, self.transferRateTimer.restart())
            bytesSinceLast = bytesTransferred - self.transferredBytesAtTimerStart
            self.transferredBytesAtTimerStart = bytesTransferred
            # bytes per millisecond -> kiB per second
            self.transferRate = bytesSinceLast * 1000 / 1024 / elapsedMs

        if transferComplete and showIndexingProgress:
            suffix = ""
            if bytesTransferred > 0:
                suffix = " " + completeMessage.format(total=totalObjects)
            self.message.emit(_("Indexing objects…") + suffix)
            self.progress.emit(0, 0)
        else:
            if totalObjects > 0:
                percent = 100 * obj / totalObjects
                rate = formatBytes(self.transferRate) if bytesTransferred > 0 else ""
                bytesStr = formatBytes(bytesTransferred)
                self.message.emit(transferingMessage.format(prct=int(percent), obj=obj, total=totalObjects, rate=rate, bytes=bytesStr))
                self.progress.emit(obj, totalObjects)
            else:
                self.message.emit(transferingMessage.format(prct=0, obj=0, total=0, rate="", bytes=""))
                self.progress.emit(0, 0)

    def update_tips(self, refname: str, old: Oid, new: Oid):
        self.updatedTips[refname] = (old, new)

    def push_update_reference(self, refname: str, message: str | None):
        if message:
            logger.error(f"Failed to push reference {refname}: {message}")

    def rememberSuccessfulKeyFile(self):
        if self.lastAttemptKey and self.lastAttemptUrl:
            strippedUrl = stripRemoteUrlPath(self.lastAttemptUrl)
            if strippedUrl:
                settings.history.workingKeys[strippedUrl] = self.lastAttemptKey
                settings.history.setDirty()
            # Clear cached passphrases if passphrase-remembering is disabled
            if not settings.prefs.rememberPassphrases:
                if self.lastAttemptKey in self.sessionPassphrases:
                    del self.sessionPassphrases[self.lastAttemptKey]
                    logger.info(f"Forgot passphrase for {self.lastAttemptKey}")
            self.lastAttemptUrl = ""
            self.lastAttemptKey = ""
            self.lastAttemptPassphrase = None
    
    def rememberSuccessfulPAT(self):
        """Remember the PAT that worked"""
        if not self.patAttempted or not self.lastAttemptUsername or not self.lastAttemptToken:
            return
            
        # Save to session
        if self.lastAttemptUrl:
            url_key = stripRemoteUrlPath(self.lastAttemptUrl)
            if url_key:
                self.sessionPATCredentials[url_key] = (self.lastAttemptUsername, self.lastAttemptToken)
                logger.info(f"Saved PAT credentials to session for {url_key}")
                
        # Also save to git config for persistence between sessions
        try:
            config = GitConfigHelper.ensure_file(GitConfigLevel.GLOBAL)
            config['credential.username'] = self.lastAttemptUsername
            config['credential.pattoken'] = self.lastAttemptToken
            logger.info(f"Saved successful PAT credentials to git config")
        except Exception as e:
            logger.warning(f"Failed to save PAT credentials to git config: {e}")

    def remoteContext(self, remote: Remote | str, resetParams=True) -> RemoteContext:
        return RemoteLink.RemoteContext(self, remote, resetParams)

    def getPassphraseFromNetworkThread(self, keyfile: str) -> str | None:
        # Check if we already have the passphrase in the session cache
        hasPassphrase = keyfile in self.sessionPassphrases
        if hasPassphrase:
            logger.info("Using passphrase from session")
            return self.sessionPassphrases[keyfile]

        # Important: is the key passphrase-protected at all?
        needsPassphrase = False
        try:
            needsPassphrase = isPrivateKeyPassphraseProtected(keyfile)
        except OSError:
            return None  # can't read key file

        if not needsPassphrase:
            return None  # doesn't need a passphrase

        # Prompt user for passphrase
        resultPassphrase = None

        def onPassphraseReady(theKeyfile, thePassphrase):
            nonlocal resultPassphrase
            if theKeyfile == keyfile and thePassphrase:
                resultPassphrase = thePassphrase
                if settings.prefs.rememberPassphrases:
                    logger.info(f"Saving passphrase for {keyfile} in session")
                    self.sessionPassphrases[keyfile] = thePassphrase

        self.requestPassphrase.emit(keyfile, onPassphraseReady)

        # Wait for passphrase to become available
        while resultPassphrase is None:
            QThread.msleep(50)
            QApplication.processEvents()
            if self._aborting:
                return None

        return resultPassphrase
    
    def getPATFromNetworkThread(self, url: str) -> tuple[str, str]:
        """
        Request Personal Access Token from UI thread
        Returns username, token tuple
        """
        result = None

        def onPATReady(username, token):
            nonlocal result
            result = (username, token)

        self.requestPAT.emit(url, onPATReady)
        
        while result is None:
            QThread.msleep(50)
            QApplication.processEvents()
            
            if self._aborting:
                return "", ""
                
        return result

    def showPassphraseDialog(self, keyfile: str, callback):
        assert onAppThread()

        parentWidget = findParentWidget(self)
        assert parentWidget

        passphraseDialog = PassphraseDialog(parentWidget, keyfile)
        passphraseDialog.passphraseReady.connect(callback)
        passphraseDialog.show()
    
    def showPATDialog(self, url: str, callback):
        """
        Show a dialog to request Personal Access Token credentials
        """
        parentWidget = findParentWidget(self)
        assert parentWidget
        
        dlg = PersonalAccessTokenDialog(parentWidget, url)
        dlg.tokenReady.connect(callback)
        dlg.open()

    def formatUpdatedTipsMessage(self, header, noNewCommits=""):
        messages = [header]

        if not self.updatedTips:
            if noNewCommits:
                messages.append(noNewCommits)
            else:
                messages.append(_("No changes."))
        else:
            for refname, (old, new) in self.updatedTips.items():
                refshort = refname.removeprefix("refs/")
                prefix = ""
                if len(self.updatedTips) > 10:
                    prefix = f"· "
                messages.append(f"{prefix}{refshort}: {shortHash(old)} → {shortHash(new)}")

        return "\n".join(messages)

    class RemoteContext:
        def __init__(self, remoteLink: RemoteLink, remote: Remote | str, resetParams=True):
            self.remoteLink = remoteLink
            self.remote = remote
            self.resetParams = resetParams

        def __enter__(self):
            # Reset login state before each remote (unless caller explicitly wants to keep initial parameters)
            if self.resetParams:
                self.remoteLink.resetLoginState()

            self.remoteLink._busy = True
            self.remoteLink._aborting = False
            self.remoteLink.updatedTips = {}

            try:
                self.remoteLink.discoverKeyFiles(self.remote)
            except (FileNotFoundError, AssertionError) as e:
                self.remoteLink.message.emit(str(e))
                raise

            return self.remoteLink

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.remoteLink._busy = False

            if not exc_type:
                # Operation was successful, remember auth credentials
                self.remoteLink.rememberSuccessfulKeyFile()
                self.remoteLink.rememberSuccessfulPAT()
            
            if exc_type and exc_type is not InterruptedError:
                # Just log the error, don't handle the exception
                logger.error(f"Remote operation failed: {exc_val}", exc_info=True)
