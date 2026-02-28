# Browser Use HUD Environment

This folder contains a deployable **HUD Environment** that adapts the Browser Use
Python SDK into plain HUD tool calls.

## Design goal

- Use Browser Use **classes directly** (`BrowserSession`, `Tools`).
- Keep HUD as the **only outer agent loop**.
- Do **not** expose Browser Use's internal agent completion loop (`done` action).
- Execute one Browser Use action per HUD tool call.

## What is exposed

- **Browser Use actions as top-level HUD tools**, for example:
  - `navigate`
  - `click`
  - `input`
  - `switch`
  - `close`
  - `search`
  - `scroll`
  - `evaluate`
  - `screenshot`
  - plus the rest of Browser Use default actions (except `done`)
- Scenarios:
  - `answer` — generic browse-and-answer with optional expected-value comparison.
  - `wiki-game` — Wikipedia link-navigation game from `start_page` to `target_page` (fewer clicks = higher reward).
- Session lifecycle is **scenario-managed** (auto-start and auto-stop inside each scenario).

By default, deployed runs force headless browser startup. Set `BROWSER_USE_ALLOW_HEADFUL=true`
only when your runtime has a real display stack.

## Why Browser Use is pinned

`browser-use==0.12.x` currently conflicts with `hud-python` on `mcp` version constraints.
This environment pins:

- `browser-use==0.11.13`
- `hud-python>=0.5.26`

to keep a resolvable environment build.

## Local usage

```bash
cd browser-use-hud-environment
python3 -m pip install -e .
hud dev env:env --stdio
```

Optional environment variables:

- `BROWSER_USE_HEADLESS` (default: `true`)
- `BROWSER_USE_EXECUTABLE_PATH` (for example `/usr/bin/chromium`)
- `BROWSER_USE_SESSION_ID` (default: `hud-browser-use-session`)
- `BROWSER_USE_ALLOWED_DOMAINS` (comma-separated, optional)
- `BROWSER_USE_PROFILE_ROOT`
- `BROWSER_USE_DOWNLOAD_ROOT`

## Deploy

```bash
cd browser-use-hud-environment
export HUD_API_KEY=your-key
hud deploy . --name browser-use-hud-environment -e HUD_API_KEY=$HUD_API_KEY
```

## Example remote task

```json
[
  {
    "env": { "name": "browser-use-hud-environment" },
    "scenario": "browser-use-hud-environment:answer",
    "args": {
      "url": "https://example.com",
      "prompt": "Open https://example.com and return the page title.",
      "expected": "Example Domain",
      "compare_mode": "contains"
    }
  },
  {
    "env": { "name": "browser-use-hud-environment" },
    "scenario": "browser-use-hud-environment:wiki-game",
    "args": {
      "start_page": "Python_(programming_language)",
      "target_page": "Guido_van_Rossum",
      "max_clicks": 8
    }
  }
]
```
