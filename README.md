# ShopeeStore

Shopee BR camisetas trend intelligence: weekly best-seller scrape, local-LLM
trend clustering, Streamlit supervision dashboard.

## Status

MVP under construction. See `AGENTS.md` for conventions and layout.

## Quickstart (once built)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
copy .env.example .env
ollama pull qwen2.5:14b-instruct
python __main__.py dashboard
```
