from dotenv import load_dotenv
import os

load_dotenv()

SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4.1-mini")
TRANSLATION_ENABLED = os.getenv("TRANSLATION_ENABLED", "true").lower() == "true"
MAX_TRANSLATION_CHARS = int(os.getenv("MAX_TRANSLATION_CHARS", "2000"))

if not SPOONACULAR_API_KEY:
    raise RuntimeError("SPOONACULAR_API_KEY não definido")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY não definido")
