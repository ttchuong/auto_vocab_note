from aqt import mw
from aqt.utils import showInfo, showWarning
from anki.notes import Note
import os
import random
import re
import unicodedata
import tempfile
import sys
import os
import requests

dir_name= ".venv/Lib/site-packages"
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), dir_name))

#import google.generativeai as genai
from google.cloud import texttospeech

# --- Configuration ---
CHIRP_VOICES = [
    {"name": "en-US-Chirp-HD-F", "lang": "en-US"},
    {"name": "en-US-Chirp-HD-D", "lang": "en-US"},
    {"name": "en-US-Chirp-HD-O", "lang": "en-US"},
    {"name": "fr-FR-Neural2-B", "lang": "fr-FR"},
    {"name": "fr-FR-Neural2-D", "lang": "fr-FR"},
]


# --- Helper Functions ---
def sanitize_filename(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = text.replace(' ', '_')
    text = re.sub(r'[^\w.-]', '', text)
    return text[:100]


def synthesize_speech(text_to_synthesize, output_filepath, language_code):
    if not text_to_synthesize.strip():
        return None

    if os.path.exists(output_filepath):
        return output_filepath

    try:
        if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
            showWarning("GOOGLE_APPLICATION_CREDENTIALS environment variable not set for TTS.")
            return None

        client = texttospeech.TextToSpeechClient()
        voice = random.choice([v for v in CHIRP_VOICES if v["lang"] == language_code])

        synthesis_input = texttospeech.SynthesisInput(text=text_to_synthesize)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=voice["lang"],
            name=voice["name"],
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config
        )

        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
        with open(output_filepath, "wb") as out:
            out.write(response.audio_content)
        return output_filepath

    except Exception as e:
        showWarning(f"Failed to synthesize speech: {str(e)}")
        return None

def gemini_generate(prompt, model="gemini-1.5-flash", api_key=None):
    """
    Send a prompt to Gemini REST API and return the generated text.
    """
    if api_key is None:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment or passed explicitly.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }

    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")

    result = resp.json()
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected Gemini API response format: {result}")

def generate_anki_data_with_gemini(word, language):

    columns = [
        "Word", "Pronunciation", "Part of Speech", "Definition",
        "Vietnamese Definition", "Register", "Example 1", "Example 1 IPA",
        "Example 2", "Example 2 IPA", "Synonyms", "Antonyms",
        "Collocations", "Connotation"
    ]

    lang_map = {"English": "English", "French": "French"}
    prompt = f"""For the word/phrase '{word}' in {lang_map[language]}, provide information for these columns:
{', '.join(columns)}
Separate columns by |. Do NOT include a header line.
For IPA, use standard IPA notation without slashes.
For 'Register', use Formal, Informal, Neutral, Slang, etc.
For 'Connotation', use Positive, Negative, Neutral, or a brief description.
If a field is not applicable, use 'N/A'.
Ensure all {len(columns)} columns are present."""

    try:
        response = gemini_generate(prompt)
        print(response)
        data = response.strip().split('|')
        return [d.strip() for d in data] + [''] * (len(columns) - len(data))
    except Exception as e:
        showWarning(f"Gemini API error: {str(e)}")
        return None


def add_note_with_audio(inputs):
    if not inputs['word']:
        showWarning("Please enter a word or phrase.")
        return

    # Generate data from Gemini
    gemini_data = generate_anki_data_with_gemini(inputs['word'], inputs['language'])
    if not gemini_data:
        return

    # Create note
    model = mw.col.models.byName(inputs['note_type'])
    if not model:
        showWarning(f"Note type {inputs['note_type']} not found.")
        return

    note = Note(mw.col, model)
    deck_id = mw.col.decks.id(inputs['deck'])
    note.model()['did'] = deck_id

    # Map Gemini data to note fields
    fields = mw.col.models.fieldNames(model)
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

    # Example 1 audio
    if len(gemini_data) > 6 and gemini_data[6]:
        sanitized_example = sanitize_filename(gemini_data[6])
        example_audio_file = f"{sanitized_example}.mp3"
        example_audio_path = os.path.join(audio_dir, example_audio_file)
        example_audio_path = synthesize_speech(gemini_data[6], example_audio_path, lang_code)
        if example_audio_path:
            final_row[9] = f"[sound:{mw.col.media.add_file(example_audio_path)}]"

    # Assign fields to note
    for i, field in enumerate(fields):
        if i < len(final_row):
            note[field] = final_row[i]

    # Add note to collection
    mw.col.addNote(note)
    mw.reset()
    showInfo("Note added successfully!")