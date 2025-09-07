# src/summarize/sonar.py
# ---------------------------------------------------------------------
# Single-pass Perplexity Sonar summarizer tuned for "executive brief"
# one-liners. Keeps output to ONE crisp sentence, normalizes dates/
# units, and includes a few safe-guards. Fast & cheap: one API call.
#
# ENV knobs (optional):
#   PPLX_API_KEY       : Perplexity API key (required)
#   PPLX_MODEL         : Model name (default: "sonar")
#   BRIEF_WORD_CAP     : Hard word cap after post-processing (default: 28)
#   BRIEF_MAX_TOKENS   : OpenAI client max_tokens (default: 60)
#
# Behavior:
#   - Active voice, no hedging, no hype
#   - Pull one material figure/date *if present* (model-side instruction)
#   - Post-fixes: ISO date → "Sep 6, 2025", "percent" → "%", "barrels per day" → "b/d"
#   - No truncation at first period (so "U.S." stays intact)
#   - Deterministic (temperature=0)
#   - Safe fallback: returns a cleaned title if the model output is junk
# ---------------------------------------------------------------------

import os
import re
from datetime import datetime
from openai import OpenAI

# ==== Prompt =================================================================

SYSTEM_PROMPT = (
    "Executive finance brief. Return exactly ONE sentence (<=28 words), no line breaks. "
    "Lead with the actor or ticker. State the concrete action or outcome. "
    "If numbers or dates appear, include ONE most material figure ($, %, units) or a specific date. "
    "Format dates as 'Sep 6, 2025' (month short name). "
    "Prefer specifics over adjectives; use active voice; avoid hedging (no may/might/could), hype, quotes, emojis, and lists. "
    'Use standard abbreviations (e.g., "U.S.", "UK", "EU"). End with a period and return only the sentence.'
)

# ==== Helpers ================================================================

def _format_iso_dates(text: str) -> str:
    """Convert ISO-like dates (YYYY-MM-DD) to 'Mon D, YYYY' (cross-platform)."""
    def repl(m):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dt = datetime(y, mo, d)
            # Windows strftime uses %#d for non-padded day; POSIX uses %-d
            day_fmt = "%#d" if os.name == "nt" else "%-d"
            return dt.strftime(f"%b {day_fmt}, %Y")
        except Exception:
            return m.group(0)

    # match 2025-09-06 or 2025-9-6 (be flexible on month/day 1-2 digits)
    return re.sub(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", repl, text)


def _tidy_units(text: str) -> str:
    """Normalize common units and punctuation spacing."""
    # "99.1 percent" -> "99.1%"  (number + optional space + 'percent')
    text = re.sub(r"(?<=\d)\s*percent\b", "%", text, flags=re.I)

    # barrels per day -> b/d
    text = re.sub(r"\bbarrels per day\b", "b/d", text, flags=re.I)

    # add space in things like "5MPs" -> "5 MPs"
    text = re.sub(r"(\d)\s*MPs\b", r"\1 MPs", text)

    # collapse spaces before punctuation  ("word , word" -> "word, word")
    text = re.sub(r"\s+([,.:;!?])", r"\1", text)

    # normalize multi-spaces
    text = re.sub(r"\s{2,}", " ", text)

    return text


def _sanitize_one_sentence(s: str, max_words: int = 28) -> str:
    """Enforce single-sentence feeling, word cap, and terminal punctuation."""
    s = " ".join((s or "").split())
    if not s:
        return s

    # Post-formatting in order
    s = _format_iso_dates(s)
    s = _tidy_units(s)

    # Hard word cap (approx) — keep it readable and deterministic
    words = s.split()
    if len(words) > max_words:
        s = " ".join(words[:max_words]).rstrip(",;:") + "."

    # Ensure ending punctuation, but don't break abbreviations like "U.S."
    if s and s[-1] not in ".!?":
        s += "."

    return s


def _looks_like_sentence(s: str) -> bool:
    """Cheap heuristic to detect junk outputs (too short, no space, bare link, etc.)."""
    s = (s or "").strip()
    if len(s) < 12:
        return False
    if " " not in s:
        return False
    if s.lower().startswith("http"):
        return False
    return True


# ==== Summarizer =============================================================

class SonarSummarizer:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        api_key = api_key or os.getenv("PPLX_API_KEY")
        if not api_key:
            raise RuntimeError("Missing PPLX_API_KEY")

        model = model or os.getenv("PPLX_MODEL", "sonar")
        self.max_tokens = int(os.getenv("BRIEF_MAX_TOKENS", "60"))
        self.word_cap = int(os.getenv("BRIEF_WORD_CAP", "28"))

        # Perplexity Sonar via OpenAI client (custom base_url)
        self.client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
        self.model = model

    def summarize_one(self, title: str, dek: str, source: str) -> str:
        """Return one tight, normalized sentence summarizing title+dek."""
        text = (title or "").strip()
        if dek:
            text += "\n\n" + dek.strip()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Source: {source}\n"
                    f"Text:\n{text}\n\n"
                    "Return only the sentence:"
                ),
            },
        ]

        try:
            out = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,   # encourages punchy output
                temperature=0,                # deterministic
            )
            content = (out.choices[0].message.content or "").strip()
            content = _sanitize_one_sentence(content, max_words=self.word_cap)

            # Fallback if the model produced junk
            if not _looks_like_sentence(content):
                fallback = _sanitize_one_sentence((title or "").strip(), max_words=self.word_cap)
                return fallback

            return content

        except Exception:
            # Last resort: cleaned title so the pipeline always ships
            return _sanitize_one_sentence((title or "").strip(), max_words=self.word_cap)
