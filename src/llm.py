import os
import time
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()
PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # gemini | claude


@lru_cache(maxsize=1)
def _gemini_client():
    """Client sirf ek baar banta hai aur reuse hota hai."""
    from google import genai

    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


@lru_cache(maxsize=1)
def _claude_client():
    import anthropic

    return anthropic.Anthropic()


def _call(system: str, user: str) -> str:
    if PROVIDER == "gemini":
        from google.genai import types

        r = _gemini_client().models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return r.text

    if PROVIDER == "claude":
        r = _claude_client().messages.create(
            model="claude-sonnet-5-5",
            max_tokens=500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text

    raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")


def generate(system: str, user: str, retries: int = 4) -> str:
    """503/429 jaise temporary errors pe ruk ruk ke retry karta hai."""
    for attempt in range(retries):
        try:
            return _call(system, user)
        except Exception as e:
            msg = str(e)
            temporary = "503" in msg or "429" in msg or "UNAVAILABLE" in msg
            if not temporary or attempt == retries - 1:
                raise
            wait = 2 ** attempt * 2  # 2s, 4s, 8s
            print(f"[retry] temporary error, {wait}s baad dobara try...")
            time.sleep(wait)