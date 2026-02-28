"""Compact HUD Environment exposing Browser Use actions as top-level tools."""

from __future__ import annotations

import logging
import os
import json
import re
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("BROWSER_USE_SETUP_LOGGING", "false")

from browser_use.agent.views import ActionResult
from browser_use.agent.prompts import AgentMessagePrompt, SystemPrompt
from browser_use.browser import BrowserSession
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.base import BaseChatModel
from browser_use.llm.openai.chat import ChatOpenAI
from browser_use.tools.service import Tools
from fastmcp.tools.tool import FunctionTool
from hud import Environment
from hud.settings import settings
from pydantic import BaseModel, ConfigDict

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(name)s | %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

env = Environment(name="browser-use-hud-environment")

HEADLESS_DEFAULT = os.getenv("BROWSER_USE_HEADLESS", "true").strip().lower()[:1] in {"1", "t", "y"}
ALLOW_HEADFUL = os.getenv("BROWSER_USE_ALLOW_HEADFUL", "false").strip().lower()[:1] in {"1", "t", "y"}
EXECUTABLE_PATH = (os.getenv("BROWSER_USE_EXECUTABLE_PATH") or "").strip()
ALLOWED_DOMAINS = [d.strip() for d in (os.getenv("BROWSER_USE_ALLOWED_DOMAINS") or "").split(",") if d.strip()]
SESSION_NAME = (os.getenv("BROWSER_USE_SESSION_ID") or "hud-browser-use-session").strip()
PROFILE_ROOT = Path(os.getenv("BROWSER_USE_PROFILE_ROOT", "/tmp/browser-use-hud/profiles"))
DOWNLOAD_ROOT = Path(os.getenv("BROWSER_USE_DOWNLOAD_ROOT", "/tmp/browser-use-hud/downloads"))
FILE_ROOT = Path(os.getenv("BROWSER_USE_FILE_ROOT", "/tmp/browser-use-hud/files"))
EXTRACTION_MODEL = os.getenv("BROWSER_USE_EXTRACTION_MODEL", "gpt-4o-mini")
EXTRACTION_BASE_URL = (os.getenv("BROWSER_USE_EXTRACTION_BASE_URL") or settings.hud_gateway_url).strip()


class Runtime(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    session: BrowserSession
    tools: Tools[None]
    file_system: FileSystem
    extraction_llm: BaseChatModel | None


RUNTIME: Runtime | None = None
BROWSER_USE_SYSTEM_PROMPT = SystemPrompt(max_actions_per_step=3).get_system_message().content
BROWSER_USE_HUD_OUTPUT = """<output>
This HUD harness uses function/tool-calling instead of Browser Use JSON envelopes.
For every step:
1) Decide your next browser action(s).
2) Call the corresponding tool directly (navigate, click, input, find_text, extract, etc.).
3) Continue iteratively until the task is complete.

Do NOT output an "action" JSON object or JSON wrapper keys like:
"thinking", "evaluation_previous_goal", "memory", "next_goal", "action".

When finished, return a normal plain-text final answer to the user.
There is no `done` tool in this harness.
</output>"""
BROWSER_USE_HUD_PROMPT = re.sub(
    r"<output>.*?</output>",
    BROWSER_USE_HUD_OUTPUT,
    BROWSER_USE_SYSTEM_PROMPT,
    count=1,
    flags=re.DOTALL,
)


def extraction_llm() -> BaseChatModel | None:
    api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("HUD_API_KEY") or settings.api_key or "").strip()
    if not api_key:
        return None
    try:
        return ChatOpenAI(
            model=EXTRACTION_MODEL,
            api_key=api_key,
            base_url=(os.getenv("OPENAI_BASE_URL") or EXTRACTION_BASE_URL or None),
        )
    except Exception as e:
        logger.warning("Extraction LLM disabled: %s", e)
        return None


def available_paths(runtime: Runtime) -> list[str]:
    paths = [str(runtime.file_system.get_dir() / name) for name in runtime.file_system.list_files()]
    paths.extend(str(path) for path in (runtime.session.downloaded_files or []) if path)
    return list(dict.fromkeys(paths))


async def stop_session(force: bool = True) -> None:
    global RUNTIME
    runtime = RUNTIME
    RUNTIME = None
    if runtime is None:
        return
    try:
        if force:
            await runtime.session.kill()
        else:
            await runtime.session.stop()
    except Exception as e:
        logger.warning("Session cleanup failed: %s", e)


def normalize_result(value: Any) -> Any:
    if isinstance(value, ActionResult):
        return value.model_dump(mode="json", exclude_none=True)
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json", exclude_none=True)
        except TypeError:
            return value.model_dump()
    return value


async def call_action(action_name: str, action_args: dict[str, Any]) -> dict[str, Any]:
    runtime = RUNTIME
    if runtime is None:
        return {"ok": False, "error": "No active session. Use browser_use_task; lifecycle is scenario-managed."}
    if action_name not in runtime.tools.registry.registry.actions:
        return {"ok": False, "error": f"Unknown Browser Use action '{action_name}'."}

    try:
        result = await runtime.tools.registry.execute_action(
            action_name=action_name,
            params=action_args,
            browser_session=runtime.session,
            page_extraction_llm=runtime.extraction_llm,
            available_file_paths=available_paths(runtime),
            file_system=runtime.file_system,
        )
        return {"ok": True, "action": action_name, "result": normalize_result(result)}
    except Exception as e:
        return {"ok": False, "action": action_name, "error": str(e)}


async def start_session(start_url: str = "") -> dict[str, Any]:
    global RUNTIME
    await stop_session(force=True)

    profile_dir = PROFILE_ROOT / SESSION_NAME
    downloads_dir = DOWNLOAD_ROOT / SESSION_NAME
    files_dir = FILE_ROOT / SESSION_NAME
    profile_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)

    session = BrowserSession(
        id=SESSION_NAME,
        is_local=True,
        headless=(HEADLESS_DEFAULT if ALLOW_HEADFUL else True),
        disable_security=True,
        user_data_dir=str(profile_dir),
        downloads_path=str(downloads_dir),
        executable_path=EXECUTABLE_PATH or None,
        allowed_domains=ALLOWED_DOMAINS or None,
        keep_alive=True,
    )
    try:
        await session.start()
    except Exception as e:
        return {"ok": False, "error": f"Failed to start Browser Use session: {e}"}

    RUNTIME = Runtime(
        session=session,
        tools=Tools(exclude_actions=["done"], output_model=None, display_files_in_done_text=False),
        file_system=FileSystem(base_dir=str(files_dir), create_default_files=True),
        extraction_llm=extraction_llm(),
    )

    if start_url.strip():
        nav = await call_action("navigate", {"url": start_url.strip(), "new_tab": False})
        if not nav.get("ok"):
            return {"ok": False, "error": f"Session started but navigation failed: {nav.get('error')}"}

    return {"ok": True}


def register_action_tools() -> None:
    template = Tools(exclude_actions=["done"], output_model=None, display_files_in_done_text=False)
    for action_name, action in template.registry.registry.actions.items():
        async def run_tool(_action_name: str = action_name, **kwargs: Any) -> dict[str, Any]:
            return await call_action(_action_name, kwargs)

        env.add_tool(
            FunctionTool(
                name=action_name,
                description=action.description or f"Browser Use action '{action_name}'",
                parameters=action.param_model.model_json_schema(),
                fn=run_tool,
            )
        )


register_action_tools()


def compare_answers(actual: Any, expected: Any, mode: str = "exact") -> float:
    if actual is None:
        return 0.0
    actual_str = str(actual).strip()
    expected_str = str(expected).strip()

    if mode == "exact":
        return 1.0 if actual_str.lower() == expected_str.lower() else 0.0
    if mode == "contains":
        return 1.0 if expected_str.lower() in actual_str.lower() else 0.0
    if mode == "json":
        try:
            actual_json = json.loads(actual_str) if isinstance(actual, str) else actual
            expected_json = json.loads(expected_str) if isinstance(expected, str) else expected
            return 1.0 if actual_json == expected_json else 0.0
        except (json.JSONDecodeError, TypeError):
            return 0.0
    if mode == "numeric":
        try:
            actual_nums = re.findall(r"-?\d+\.?\d*", actual_str)
            expected_nums = re.findall(r"-?\d+\.?\d*", expected_str)
            if actual_nums and expected_nums:
                return 1.0 if float(actual_nums[0]) == float(expected_nums[0]) else 0.0
            return 0.0
        except (ValueError, IndexError):
            return 0.0
    if mode == "regex":
        try:
            return 1.0 if re.search(expected_str, actual_str, re.IGNORECASE) else 0.0
        except re.error:
            return 0.0
    return 0.0


async def render_harness_prompt(task: str) -> str:
    runtime = RUNTIME
    if runtime is None:
        return (
            f"{BROWSER_USE_HUD_PROMPT}\n\n"
            f"<agent_state_unavailable>Browser runtime not available.</agent_state_unavailable>\n"
            f"USER TASK:\n{task}"
        )
    state = await runtime.session.get_browser_state_summary(
        include_screenshot=False,
        include_recent_events=False,
    )
    browser_use_input = AgentMessagePrompt(
        browser_state_summary=state,
        file_system=runtime.file_system,
        task=task,
        include_recent_events=False,
    ).get_user_message(use_vision=False)
    browser_use_input_text = (
        browser_use_input.content if isinstance(browser_use_input.content, str) else str(browser_use_input.content)
    )
    return f"{BROWSER_USE_HUD_PROMPT}\n\n{browser_use_input_text}"


@env.scenario("answer")
async def answer(
    url: str,
    prompt: str,
    expected: Any | None = None,
    compare_mode: str = "exact",
) -> Any:
    """Generic browser task returning an answer."""
    setup = await start_session(start_url=url)
    if not setup.get("ok"):
        _ = yield f"Browser session setup failed: {setup.get('error')}\nRespond with a brief failure message."
        yield 0.0
        return

    agent_answer = ""
    try:
        agent_answer = yield await render_harness_prompt(prompt)
    finally:
        await stop_session(force=True)

    if expected is None:
        yield 1.0
        return
    yield compare_answers(agent_answer, expected, compare_mode)


@env.scenario("wiki-game")
async def wiki_game(
    start_page: str,
    target_page: str,
    max_clicks: int = 10,
    prompt: str | None = None,
) -> Any:
    """Wikipedia click-only navigation game with efficiency reward."""
    start_url = f"https://en.wikipedia.org/wiki/{start_page}"
    target_fragment = f"/wiki/{target_page}".lower()
    task_prompt = prompt or (
        f"Wikipedia Speedrun Challenge!\n\n"
        f"Starting article: {start_page.replace('_', ' ')}\n"
        f"Target article: {target_page.replace('_', ' ')}\n\n"
        "Navigate from the starting article to the target article by clicking links.\n"
        "You may use only link clicks within article content (no search, no back button).\n"
        f"Try to reach the target in as few clicks as possible. Maximum clicks: {max_clicks}."
    )

    setup = await start_session(start_url=start_url)
    if not setup.get("ok"):
        _ = yield f"Browser session setup failed: {setup.get('error')}\nRespond with a brief failure message."
        yield 0.0
        return

    final_url = ""
    clicks = max_clicks
    try:
        _ = yield await render_harness_prompt(task_prompt)
        runtime = RUNTIME
        if runtime is not None:
            state = await runtime.session.get_browser_state_summary(
                include_screenshot=False,
                include_recent_events=False,
            )
            final_url = (state.url or "").strip()
        hist = await call_action("evaluate", {"code": "window.history.length"})
        if hist.get("ok"):
            text = str((hist.get("result") or {}).get("extracted_content", ""))
            nums = re.findall(r"\d+", text)
            if nums:
                clicks = max(1, int(nums[0]) - 1)
    finally:
        await stop_session(force=True)

    if target_fragment in final_url.lower():
        max_clicks = max(1, int(max_clicks))
        if clicks <= max_clicks:
            reward = max(0.1, 1.0 - (clicks - 1) / max_clicks)
        else:
            reward = 0.1
    else:
        reward = 0.0
    yield reward


if __name__ == "__main__":
    env.run(transport="stdio")
