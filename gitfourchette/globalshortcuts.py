# -----------------------------------------------------------------------------
# Copyright (C) 2025 Iliyas Jorio.
# This file is part of GitFourchette, distributed under the GNU GPL v3.
# For full terms, see the included LICENSE file.
# -----------------------------------------------------------------------------

"""
Keyboard shortcuts for the application.

GlobalShortcuts is a collection of constants used throughout the application.
"""

from gitfourchette.qt import QKeySequence


NO_SHORTCUT = []
MultiShortcut = list[str]


class GlobalShortcuts:
    find: MultiShortcut = NO_SHORTCUT
    findNext: MultiShortcut = NO_SHORTCUT
    findPrevious: MultiShortcut = NO_SHORTCUT
    openRepoFolder: MultiShortcut = NO_SHORTCUT
    refresh: MultiShortcut = NO_SHORTCUT
    stageHotkeys: MultiShortcut = NO_SHORTCUT
    discardHotkeys: MultiShortcut = NO_SHORTCUT

    @classmethod
    def setup(cls):
        def makeMultiShortcut(shortcut: str | QKeySequence | None) -> MultiShortcut:
            if not shortcut:
                return []

            shortcuts = []
            stdKeyPlus = 'Alt+' if QKeySequence.keyBindings(QKeySequence.StandardKey.Find) else ''

            if 'Ctrl+' in shortcut:
                variants = [
                    shortcut,  # normal Ctrl
                    shortcut.replace('Ctrl+', 'Meta+'),  # macOS cmd
                    shortcut.replace('Ctrl+', stdKeyPlus),  # native platform shortcut, such as alt+f on some macOS versions
                ]
                shortcuts.extend(variants)
            else:
                shortcuts.append(shortcut)

            return shortcuts

        cls.find = makeMultiShortcut("Ctrl+F")
        cls.findNext = makeMultiShortcut("F3")
        cls.findPrevious = makeMultiShortcut("Shift+F3")
        cls.openRepoFolder = makeMultiShortcut("Shift+Alt+O")
        cls.refresh = makeMultiShortcut("F5")
        cls.stageHotkeys = makeMultiShortcut("Ctrl+S")
        cls.discardHotkeys = makeMultiShortcut("Ctrl+D")
