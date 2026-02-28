# Browser Use HUD Environment

A fully functional [HUD](https://hud.ai) environment that wraps the [Browser Use](https://github.com/browser-use/browser-use) Python SDK into tool calls. Every Browser Use action (`navigate`, `click`, `input`, `scroll`, `evaluate`, etc.) is exposed as a top-level HUD tool.

Includes two scenarios out of the box:

- **`answer`** — browse to a URL, complete a task, optionally compare against an expected answer.
- **`wiki-game`** — navigate Wikipedia from a start page to a target page using only link clicks (fewer clicks = higher reward).

## Using this with HUD

**Run locally** — install and launch the MCP server:

```bash
pip install -e .
hud dev env:env
```

**Deploy** — push to the HUD platform:

```bash
hud deploy
```

**Train** — create tasks from your scenarios on [hud.ai](https://hud.ai), run evals across models, then train directly on successful traces. Fork a base model at [hud.ai/models](https://hud.ai/models), select a taskset, and the platform handles fine-tuning — each run produces a new checkpoint you can set as HEAD and use immediately.

See the [HUD docs](https://docs.hud.ai) for the full workflow: [Environments](https://docs.hud.ai/platform/environments) · [Tasks & Training](https://docs.hud.ai/quick-links/evals) · [Models](https://docs.hud.ai/platform/models)

## Extending

Fork this repo and edit `env.py` to add new tools, scenarios, or scoring logic. The environment auto-registers every Browser Use action at import time — add your own with `@env.tool()` or `@env.scenario()`.
