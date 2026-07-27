"""Print filter: decide from a product TITLE whether the shirt has a print.

Rules (see PHASE3_PLAN.md):
- PLAIN hints (lisa, basica, dry fit, malha fria, canelada, gola alta, ...)
  mark the shirt as having no print.
- PRINT hints (estampada, bordada, anime, kpop, caveira, tema, ...) WIN over
  plain hints when both appear ("Basica com Estampa Grafica" is printed).
- No hint at all -> NOT plain (keep; the LLM clustering decides).

Pure module: no LLM, no DB, regex only. Unit-tested against real scraped titles.
"""

from __future__ import annotations

import re
import unicodedata

PLAIN_RE = re.compile(
    r"\b(lisas?|b[aá]sicas?|basic[ao]s?|dry[\s-]?fit\w*|malha\s?fria|canelad[ao]s?"
    r"|gola\s?alta|gola\s?o\b|seamless|sem\s?estampa)\b",
    re.IGNORECASE,
)

PRINT_RE = re.compile(
    r"\b(estampa|bordad|personagem|animes?\b|mang[aá]s?\b|k-?pop|memes?\b|frases?\b"
    r"|engra[cç]ad|logos?\b|caveira|florais?\b|flores\b|estilo\s?americano|temas?\b"
    r"|g[óo]tic|tie[\s-]?dye|camuflad|desenho|ilustra)",
    re.IGNORECASE,
)


def is_plain(title: str) -> bool:
    """True if the title describes a plain (printless) shirt."""
    if PRINT_RE.search(title):
        return False
    return bool(PLAIN_RE.search(title))


def theme_slug(theme: str) -> str:
    """'Academia/Fitness' -> 'academia-fitness'; 'Nostalgia Anos 80/90' ->
    'nostalgia-anos-80-90'. ASCII, lowercase, hyphen-separated."""
    normalized = unicodedata.normalize("NFKD", theme.strip().lower())
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug or "sem-tema"
