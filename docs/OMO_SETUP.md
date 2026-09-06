# OmO Setup Handoff

This file preserves the setup decisions and next steps across an OpenCode
restart. It documents the development harness only; the ShopeeStore
application must continue using local Ollama at runtime.

## Decision

- Install the Ultimate OmO edition for OpenCode only.
- Use OpenCode Go as the only configured provider.
- Do not install Codex Light; Codex CLI is not part of this workflow.
- Keep the installation user-level. Do not commit OmO-generated user config.
- Do not install OmO marketplace skills such as `hyperplan`,
  `pre-publish-review`, or `work-with-pr`; they target OmO's own release
  workflow and do not match this Python project.
- Accept that Go-only Sisyphus and Hephaestus routing may require more
  iterations than their preferred Claude/OpenAI provider paths.

## Project Rules

- The app's LLM is local Ollama only, configured through `LLM_MODEL`.
- OmO is a development-time coding harness and is separate from the app's
  runtime LLM.
- Preserve the repository's curated skills:
  - `.opencode/skills/agent-ledger-pattern/`
  - `.opencode/skills/ptbr-title-clustering/`
  - `.opencode/skills/shopee-br-scraping/`
- Use `ruff check .` and `pytest` after Python changes.
- Run a configured type checker when one exists.

## Pre-Install State

- OpenCode: `1.18.13` (OmO requires `>=1.4.0`)
- Node: `v22.20.0`
- npm: `11.16.0`
- Bun: `1.3.14` installed during this setup
- Platform: native Windows PowerShell 5.1
- Git Bash: not required for OpenCode Ultimate; it is required by the Codex
  Light Windows path.

## Install Steps

Run these steps from a fresh PowerShell after this document is committed or
otherwise preserved:

1. Install Bun:

   ```powershell
   powershell -c "irm bun.sh/install.ps1 | iex"
   ```

2. Open a fresh terminal so Bun is on `PATH`.

3. Install OmO for OpenCode with Go-only routing:

   ```powershell
   bunx oh-my-openagent install --no-tui --platform=opencode --claude=no --openai=no --gemini=no --copilot=no --opencode-go=yes --skip-auth
   ```

   If the installer reports that authentication is required, rerun without
   `--skip-auth` and complete the OpenCode Go login flow.

4. Verify the installation:

   ```powershell
   bunx oh-my-openagent doctor
   ```

5. Restart OpenCode. Confirm the OmO plugin loads, then smoke-test with a
   small task using `ultrawork` or `ulw`.

## Installation Result

- OmO `4.19.4` is installed and loaded by OpenCode `1.18.13`.
- Bun `1.3.14` is installed at `C:\Users\NetoS\.bun\bin\bun.exe`.
- The OmO doctor JSON result has `exitCode: 0`.
- Configuration is valid and the OpenCode/TUI plugin entries are registered.
- All configured user overrides use `opencode-go/*` models, including
  Hephaestus on `opencode-go/gpt-5.6-luna`.
- LSP, comment-checker, websearch, Context7, grep.app, and the model registry
  are available.
- Anonymous OmO telemetry is enabled by default. Disable it with
  `OMO_DISABLE_POSTHOG=1` or `OMO_SEND_ANONYMOUS_TELEMETRY=0` if desired.
- AST-grep is not provisioned because the published package did not include
  its Windows install script. It is optional for normal coding tasks.
- GitHub CLI (`gh`) is not installed. It is optional unless GitHub automation
  is needed.
- The doctor reports `fallback_models` as deprecated, but replacing those keys
  with `models` made the current `[opencode].agents` configuration invalid.
  The valid fallback configuration is preserved; do not run `config migrate`
  again until this OmO version resolves that mismatch.

The current OmO user-level files are:

- `C:\Users\NetoS\.omo\omo.jsonc`
- `C:\Users\NetoS\.config\opencode\opencode.jsonc`
- `C:\Users\NetoS\.config\opencode\tui.json`

## Expected User-Level Changes

OmO was configured outside this repository. No OmO-generated project config,
provider credentials, or auth state was added to ShopeeStore.

Do not add provider credentials, auth state, or generated model configuration
to this repository.

## Windows Notes

- OpenCode Ultimate uses the Bun-based installer and does not require Git Bash.
- If Bun is not visible after installation, start a new PowerShell session.
- If OmO reports a Windows proxy error involving `fetch() proxy.url`, follow
  the official Windows preinstall workaround before rerunning `doctor`:

  ```powershell
  npm install oh-my-openagent@latest --prefix "$env:APPDATA\opencode"
  ```

- Do not use `npm install -g`, `bun add -g`, or `bun install -g` for OmO.

## After OmO Is Verified

- Keep the repository's existing Python-specific skills as the source of truth.
- Use `grill-me` for adversarial review of the upcoming refactor plan.
- Break the refactor into atomic slices that keep `ruff check .` and `pytest`
  green.
- Ask before running `/init-deep`; it generates additional `AGENTS.md` files in
  the repository.
- Restart OpenCode and complete the smoke test before resuming the refactor
  survey and planning.

## Resume Point

After an OpenCode restart, read this file first. Then:

1. Start OpenCode from a fresh PowerShell session.
2. Confirm the OmO startup/plugin message appears.
3. Run a small, non-destructive task containing `ultrawork` or `ulw`.
4. If the smoke test passes, use `grill-me` to review the refactor plan before
   changing application code.
