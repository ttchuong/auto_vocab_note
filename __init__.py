from aqt import mw
from aqt.qt import QAction, QKeySequence
from .gui import AddNoteDialog

def init():
    action = QAction("Auto-create vocab by Gemini", mw)
    action.setShortcut(QKeySequence("Ctrl+G"))
    action.triggered.connect(lambda: AddNoteDialog(mw).exec())
    mw.form.menuTools.addAction(action)

init()
