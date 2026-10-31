import os
import random
import time
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()
PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # gemini | claude

TEMP_ERRORS = ("503", "429", "UNAVAILABLE", "timed out", "Timeout", "overloaded")


def _model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


@lru_cache(maxsize=1)
def _gemini_client():
    """Client sirf ek baar banta hai aur reuse hota hai."""
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        http_options=types.HttpOptions(timeout=30000),  # 30 sec
    )


@lru_cache(maxsize=1)
def _claude_client():
    import anthropic

    return anthropic.Anthropic()


def _retry(fn, retries: int = 5):
    """Temporary errors (503/429/timeout) pe backoff ke saath retry. Permanent errors turant raise."""
    last_err = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if not any(s in str(e) for s in TEMP_ERRORS):
                raise
            if attempt == retries - 1:
                break  # aakhri try ke baad sleep nahi
            wait = min(2 ** (attempt + 1), 20) + random.random()  # 2s, 4s, 8s, 16s
            print(f"[retry] model busy, {wait:.0f}s baad dobara... ({attempt + 1}/{retries})")
            time.sleep(wait)
    raise last_err

def generate(system: str, user: str) -> str:
    """Simple text generation (RAG ke liye)."""
    if PROVIDER == "claude":
        r = _claude_client().messages.create(
            model="claude-sonnet-5-5",
            max_tokens=500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text

    if PROVIDER != "gemini":
        raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")

    from google.genai import types

    def call():
        r = _gemini_client().models.generate_content(
            model=_model(),
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return r.text

    return _retry(call)


def gemini_step(contents, system: str, tools: list):
    """Ek agent turn (tool-calling ke saath). SDK ki auto function-calling band, loop hum chalate hain."""
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    def call():
        return _gemini_client().models.generate_content(
            model=_model(),
            contents=contents,
            config=config,
        )

    return _retry(call)