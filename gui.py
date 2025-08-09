from aqt.qt import QDialog, QVBoxLayout, QLabel, QLineEdit, QComboBox, QDialogButtonBox
from aqt import mw
from .core import add_note_with_audio

class AddNoteDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Add New Note with Audio")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Word input
        self.word_input = QLineEdit()
        layout.addWidget(QLabel("Word/Phrase:"))
        layout.addWidget(self.word_input)

        # Language dropdown
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "French"])
        layout.addWidget(QLabel("Language:"))
        layout.addWidget(self.language_combo)

        # Note type dropdown
        self.note_type_combo = QComboBox()
        note_types = [model['name'] for model in mw.col.models.all()]  # Changed from model.name to model['name']
        self.note_type_combo.addItems(note_types)
        layout.addWidget(QLabel("Note Type:"))
        layout.addWidget(self.note_type_combo)

        # Deck dropdown
        self.deck_combo = QComboBox()
        decks = [deck['name'] for deck in mw.col.decks.all()]  # Changed from d['name'] (already correct, kept for clarity)
        self.deck_combo.addItems(decks)
        layout.addWidget(QLabel("Deck:"))
        layout.addWidget(self.deck_combo)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def accept(self):
        inputs = {
            'word': self.word_input.text().strip(),
            'language': self.language_combo.currentText(),
            'note_type': self.note_type_combo.currentText(),
            'deck': self.deck_combo.currentText()
        }
        add_note_with_audio(inputs)
        super().accept()