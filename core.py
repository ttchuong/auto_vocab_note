from aqt import mw
from aqt.utils import showInfo, showWarning
from anki.notes import Note
import os
import random
import re
import unicodedata
import tempfile
import requests
import base64

""" 
import sys
dir_name= ".venv/Lib/site-packages"
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), dir_name))

#import google.generativeai as genai
from google.cloud import texttospeech
"""

# --- Configuration ---
CHIRP_VOICES = [
    {"name": "en-US-Chirp-HD-F", "lang": "en-US"},
    {"name": "en-US-Chirp-HD-D", "lang": "en-US"},
    {"name": "en-US-Chirp-HD-O", "lang": "en-US"},
    {"name": "fr-FR-Chirp3-HD-Achird", "lang": "fr-FR"},
    {"name": "fr-FR-Chirp3-HD-Aoede", "lang": "fr-FR"},
    {"name": "fr-FR-Chirp3-HD-Callirrhoe", "lang": "fr-FR"},
    {"name": "fr-FR-Chirp3-HD-Fenrir", "lang": "fr-FR"},
]

# This must match the field names in the note type
ANKI_COLUMNS = [
    "Word", "Pronunciation", "Word Audio", "Part of Speech", "Definition", "Vietnamese Definition",
    "Register", "Example 1", "Example 1 IPA", "Example 1 Audio", "Example 2", "Example 2 IPA",
    "Synonyms", "Antonyms", "Collocations", "Connotation", "Image"
]
ANKI_COLUMNS_FR = [
    "Mot", "Prononciation", "Audio du mot", "Partie du discours", "Définition", "Définition en vietnamien",
    "Registre", "Exemple 1", "API de l'exemple 1", "Audio de l'exemple 1", "Exemple 2", "API de l'exemple 2",
    "Synonymes", "Antonymes", "Collocations", "Connotation", "Image"
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

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        showWarning("GEMINI_API_KEY environment variable not set for TTS.")
        return None

    try:
        # Pick a random voice from CHIRP_VOICES for the given language
        voices = [v for v in CHIRP_VOICES if v["lang"] == language_code]
        if not voices:
            showWarning(f"No matching voices found for language {language_code}.")
            return None
        voice = random.choice(voices)

        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
        body = {
            "input": {"text": text_to_synthesize},
            "voice": {
                "languageCode": voice["lang"],
                "name": voice["name"],
            },
            "audioConfig": {
                "audioEncoding": "MP3"
            }
        }

        resp = requests.post(url, json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"TTS request failed: {resp.status_code} {resp.text}")

        audio_content = resp.json().get("audioContent")
        if not audio_content:
            raise RuntimeError("No audio content in TTS response.")

        os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
        with open(output_filepath, "wb") as out:
            out.write(base64.b64decode(audio_content))

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

def generate_anki_data_with_gemini(word, language, example1=""):
    org_cols = ANKI_COLUMNS if language == "English" else ANKI_COLUMNS_FR
    columns = [item for idx, item in enumerate(org_cols) if idx not in {2, 9}] 

    prompt = ""
    if language == "French":
         prompt = f"""Pour le mot/l'expression '{word}' en {language}, veuillez fournir des informations pour ces colonnes :
{', '.join(columns)}
Séparez les colonnes par |. N'incluez PAS de ligne d'en-tête.
Pour l'API, utilisez la notation API standard. N'utilisez pas de barres obliques dans les champs API.
Pour 'Registre', utilisez Formel, Informel, Neutre.
Pour 'Connotation', utilisez Positive, Négative, Neutre.
Si un champ n'est pas pertinent, utilisez 'N/A'.
'Image' est blanche.
{example1 and f'Exemple 1 est {example1}'}
Assurez-vous que les {len(columns)} colonnes sont toutes présentes."""
    else:
        prompt = f"""For the word/phrase '{word}' in {language}, provide information for these columns:
{', '.join(columns)}
Separate columns by |. Do NOT include a header line.
For IPA, use standard IPA notation. Don't use slashes in IPA fields.
For 'Register', use Formal, Informal, Neutral.
For 'Connotation', use Positive, Negative, Neutral.
'Image' is blank.
{example1 and f'Example 1 is {example1}'}
If a field is not applicable, use 'N/A'.
Ensure all {len(columns)} columns are present."""
    
    try:
        response = gemini_generate(prompt)
        data = response.strip().split('|')
        return [d.strip() for d in data] + [''] * (len(columns) - len(data))
    except Exception as e:
        showWarning(f"Gemini API error: {str(e)}")
        return None

def get_first_google_image(word, language="English"):
    """
    Search Google Images and return the local file path of the first result.
    Requires: Google Custom Search API enabled.
    """
    url = "https://www.googleapis.com/customsearch/v1"
    api_key = os.environ.get("GEMINI_API_KEY")
    cx_id = "e5e89ca3ff5224384"
    lang_map = {
        "English": "en",
        "French": "fr"
    }
    lang_code = lang_map.get(language, "en")
    params = {
        "q": word,
        "cx": cx_id,
        "key": api_key,
        "searchType": "image",
        "num": 1,
        "safe": "active",
        "lr": f"lang_{lang_code}"  # Language restriction
    }
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"Google Image search failed: {resp.text}")

    items = resp.json().get("items", [])
    if not items:
        return None

    items = resp.json().get("items", [])
    if not items:
        return None

    img_url = items[0]["link"]

    # Remove query parameters from URL for file extension parsing
    clean_url = img_url.split("?")[0]
    ext = os.path.splitext(clean_url)[-1].lower()

    # Validate extension
    if not ext or len(ext) > 5:
        ext = ".jpg"

    img_resp = requests.get(img_url)
    if img_resp.status_code != 200:
        return None

    tmp_filename = f"{word}{ext}".replace(" ", "_")
    tmp_path = os.path.join(tempfile.gettempdir(), tmp_filename)

    with open(tmp_path, "wb") as f:
        f.write(img_resp.content)

    return tmp_path


