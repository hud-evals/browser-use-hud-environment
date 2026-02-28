# Browser Use HUD Environment

A fully functional [HUD](https://hud.ai) environment that wraps the [Browser Use](https://github.com/browser-use/browser-use) Python SDK into tool calls. Every Browser Use action (`navigate`, `click`, `input`, `scroll`, `evaluate`, etc.) is exposed as a top-level HUD tool — no JSON wrappers, no internal agent loop.

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

**Evaluate** — create tasks in `tasks.json` (or on the platform), then run evals against any model. Results feed into the HUD leaderboard and can be used to train agents with RL.

See the [HUD docs](https://docs.hud.ai) for the full workflow: [Environments](https://docs.hud.ai/platform/environments) · [CLI Reference](https://docs.hud.ai/reference/cli/overview) · [Evaluation Guide](https://docs.hud.ai/quick-links/environments)

## Extending

Fork this repo and edit `env.py` to add new tools, scenarios, or scoring logic. The environment auto-registers every Browser Use action at import time — add your own with `@env.tool()` or `@env.scenario()`.
