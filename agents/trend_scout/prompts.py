"""PT-BR prompts for title clustering.

Contract (see .opencode/skills/ptbr-title-clustering/SKILL.md):
- max 25 numbered titles per call
- strict JSON back: {"clusters": [{"theme": str, "indices": [int], "why": str}]}
"""

CLUSTER_SYSTEM = """Voce agrupa titulos de produtos de e-commerce brasileiro (Shopee) por TEMA.

Regras:
- Agrupe por tema/estetica da estampa, NAO por atributo do produto (tecido, cor, kit).
- Temas tipicos: memes, frases engracadas, nostalgia anos 80/90, evangelicas,
  academia/fitness, pets, profissoes, anime/geek, kpop, festas sazonais,
  esportes, casal, basica/lisa, streetwear.
- Temas em pt-BR, curtos (2-4 palavras), minusculas.
- Um titulo pode ficar fora de todos os clusters (ruido) - isso e esperado.
- Responda SOMENTE com JSON valido no formato:
  {"clusters": [{"theme": "tema", "indices": [1, 5], "why": "uma frase"}]}
- "indices" referencia os numeros dos titulos enviados."""


def cluster_user_prompt(titles: list[str]) -> str:
    """Numbered title list for one batch (caller enforces max 25)."""
    lines = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    return f"Agrupe estes titulos por tema:\n\n{lines}"
