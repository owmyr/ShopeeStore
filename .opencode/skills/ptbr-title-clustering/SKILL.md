---
name: ptbr-title-clustering
description: PT-BR e-commerce title clustering prompt patterns for small local Ollama models - 25-title batches, strict JSON output, Brazilian slang/meme awareness, retry discipline. Use ONLY when working on agents/trend_scout/prompts.py, agents/trend_scout/analyzer.py, or core/llm.py.
---

# PT-BR title clustering with small local LLMs

## Hard constraints
- NEVER send more than 25 product titles per LLM call. Batch in
  `analyzer.py`; loop over batches and merge results.
- Model comes from config (`LLM_MODEL`). Never hardcode a model name.
- `temperature=0.2`, request JSON format output (Ollama `format: "json"`).

## Prompt contract
- Titles are numbered 1..N in the user message, one per line.
- Demand STRICT JSON only, no prose, no markdown fences:

```json
{"clusters": [{"theme": "short-pt-br-slug", "indices": [1, 5, 9], "why": "uma frase"}]}
```

- `indices` must be a subset of the numbers sent; a title may be left
  unclustered (noise) - that is fine and expected.

## PT-BR awareness (put these hints in the system prompt)
- Titles are Brazilian e-commerce keyword spam: "camiseta oversized
  streetwear", "kit 3 unidades", "algodao fio 30.1", "frete gratis".
- Cluster by THEME, not by product attributes: memes, frases engracadas,
  nostalgia anos 80/90, evangelicas, pets, profissao,
  anime/geek, festas (Sao Joao, Carnaval), esportes, casal.
- Themes must be in pt-BR, short (2-4 words), lowercase slug style.
- PLAIN SHIRTS (lisa/basica/dry fit/malha fria/gola alta/canelada) get the
  reserved theme `nao-estampada` - never a real theme. We sell prints.

## Failure discipline
- On invalid JSON: retry ONCE with a stricter prompt ("Responda SOMENTE com
  JSON valido"). If it still fails, log and mark the batch as unclustered -
  never crash the run on LLM output.
- Validate with `json.loads` + pydantic model before merging.
