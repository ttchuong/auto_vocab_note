from aqt.qt import QDialog, QVBoxLayout, QLabel, QLineEdit, QComboBox, QDialogButtonBox
from aqt import mw
from aqt.utils import showInfo, showWarning
from anki.notes import Note
import tempfile
import os

# Import gemini_utils from your first add-on folder
from .core import (
    generate_anki_data_with_gemini,
    synthesize_speech,
    sanitize_filename,
    get_first_google_image,
    ANKI_COLUMNS,
    ANKI_COLUMNS_FR,
)

def add_note_with_audio(inputs):
    if not inputs['word']:
        showWarning("Please enter a word or phrase.")
        return

    # Generate data from Gemini
    gemini_data = generate_anki_data_with_gemini(inputs['word'], inputs['language'], inputs['example1'])
    if not gemini_data:
        return

    # Create note
    model = mw.col.models.by_name(inputs['note_type'])
    if not model:
        showWarning(f"Note type {inputs['note_type']} not found.")
        return

    note = Note(mw.col, model)
    deck_id = mw.col.decks.id(inputs['deck'])
    note.note_type()['did'] = deck_id

    # Map Gemini data to note fields
    fields = mw.col.models.field_names(model)
    final_row = [''] * max(16, len(fields))  # Ensure enough fields

    field_map = {
        0: 0,  # Word
        1: 1,  # Pronunciation
        3: 2,  # Part of Speech
        4: 3,  # Definition
        5: 4,  # Vietnamese Definition
        6: 5,  # Register
        7: 6,  # Example 1
        8: 7,  # Example 1 IPA
        10: 8,  # Example 2
        11: 9,  # Example 2 IPA
        12: 10,  # Synonyms
        13: 11,  # Antonyms
        14: 12,  # Collocations
        15: 13  # Connotation
    }

    for final_idx, gemini_idx in field_map.items():
        if final_idx < len(fields) and gemini_idx < len(gemini_data):
            final_row[final_idx] = gemini_data[gemini_idx]

    # Generate audio files
    temp_dir = tempfile.gettempdir()
    audio_dir = os.path.join(temp_dir, "anki_audio")
    os.makedirs(audio_dir, exist_ok=True)

    lang_code = "en-US" if inputs['language'] == "English" else "fr-FR"
    word_audio_path = None
    example_audio_path = None

    # Word audio
    if inputs['word']:
        sanitized_word = sanitize_filename(inputs['word'])
        word_audio_file = f"{sanitized_word}.mp3"
        word_audio_path = os.path.join(audio_dir, word_audio_file)
        word_audio_path = synthesize_speech(inputs['word'], word_audio_path, lang_code)
        if word_audio_path:
            final_row[2] = f"[sound:{mw.col.media.add_file(word_audio_path)}]"

    # Example 1 (manual or Gemini)
    #example_text =  or (gemini_data[6] if len(gemini_data) > 6 else "")

    # Example 1
    if gemini_data[6]:
        example_text = gemini_data[6]
        sanitized_example = sanitize_filename(example_text)
        example_audio_file = f"{sanitized_example}.mp3"
        example_audio_path = os.path.join(audio_dir, example_audio_file)
        example_audio_path = synthesize_speech(example_text, example_audio_path, lang_code)
        if example_audio_path:
            final_row[9] = f"[sound:{mw.col.media.add_file(example_audio_path)}]"

    # Assign fields to note
    for i, field in enumerate(fields):
        if i < len(final_row):
            note[field] = final_row[i]

    # Podcast (optional)
    podcast_text = inputs.get("podcast", "")
    if podcast_text:
        if "Podcast" in note:   # make sure the notetype has a Podcast field
            note["Podcast"] = podcast_text

    # Image
    if inputs['word']:
        sanitized_word = sanitize_filename(final_row[0])
        img_path = get_first_google_image(sanitized_word, inputs['language'])
        if img_path:
            note["Image"] = f'<img src="{mw.col.media.add_file(img_path)}">'

    # Add note to collection
    mw.col.addNote(note)
    mw.reset()
    showInfo("Note added successfully!")

class AddNoteDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Add New Note with Audio")
        self.resize(600, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Word input
        self.word_input = QLineEdit()
        layout.addWidget(QLabel("Word/Phrase:"))
        layout.addWidget(self.word_input)

        # Example 1 input
        self.example1_input = QLineEdit()
        layout.addWidget(QLabel("Example 1 (optional):"))
        layout.addWidget(self.example1_input)

        # Podcast input
        self.podcast_input = QLineEdit()
        layout.addWidget(QLabel("Podcast (optional):"))
        layout.addWidget(self.podcast_input)

        # Language dropdown
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "French"])
        layout.addWidget(QLabel("Language:"))
        layout.addWidget(self.language_combo)

        # Note type dropdown
        self.note_type_combo = QComboBox()
        note_types = [model['name'] for model in mw.col.models.all()]
        self.note_type_combo.addItems(note_types)
        layout.addWidget(QLabel("Note Type:"))
        layout.addWidget(self.note_type_combo)

        # Deck dropdown
        self.deck_combo = QComboBox()
        decks = [deck['name'] for deck in mw.col.decks.all()]
        self.deck_combo.addItems(decks)
        layout.addWidget(QLabel("Deck:"))
        layout.addWidget(self.deck_combo)

        # Load saved preferences
        self.load_preferences()

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def load_preferences(self):
        # Load saved preferences from mw.col.conf
        conf = mw.col.conf.get("anki_audio_note", {})

        # Set language default
        saved_language = conf.get("language")
        if saved_language in ["English", "French"]:
            index = self.language_combo.findText(saved_language)
            if index >= 0:
                self.language_combo.setCurrentIndex(index)

        # Set note type default
        saved_note_type = conf.get("note_type")
        if saved_note_type and saved_note_type in [model['name'] for model in mw.col.models.all()]:
            index = self.note_type_combo.findText(saved_note_type)
            if index >= 0:
                self.note_type_combo.setCurrentIndex(index)

        # Set deck default
        saved_deck = conf.get("deck")
        if saved_deck and saved_deck in [deck['name'] for deck in mw.col.decks.all()]:
            index = self.deck_combo.findText(saved_deck)
            if index >= 0:
                self.deck_combo.setCurrentIndex(index)

    def accept(self):
        inputs = {
            'word': self.word_input.text().strip(),
            'language': self.language_combo.currentText(),
            'note_type': self.note_type_combo.currentText(),
            'deck': self.deck_combo.currentText(),
            'example1': self.example1_input.text().strip(),
            "podcast": self.podcast_input.text().strip(),
        }

        # Save preferences
        mw.col.conf["anki_audio_note"] = {
            "language": inputs["language"],
            "note_type": inputs["note_type"],
            "deck": inputs["deck"]
        }
        
        add_note_with_audio(inputs)
        super().accept()