from aqt import mw
from aqt.qt import QAction
from .gui import AddNoteDialog

def init():
    action = QAction("Add Note with Audio", mw)
    action.triggered.connect(lambda: AddNoteDialog(mw).exec())
    mw.form.menuTools.addAction(action)

init()
