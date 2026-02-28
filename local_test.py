"""Local checks for Browser Use HUD environment wiring."""

from __future__ import annotations

import asyncio
import os

from env import answer, env


async def main() -> None:
    await env.list_tools()
    tool_names = [tool.name for tool in env.as_tools()]
    print("Registered tools:", ", ".join(sorted(tool_names)))
    print("Has browser_use_start:", "browser_use_start" in tool_names)
    print("Has browser_use_state:", "browser_use_state" in tool_names)
    print("Has browser_use_stop:", "browser_use_stop" in tool_names)

    if os.getenv("BROWSER_USE_RUN_SMOKE", "").strip().lower() not in {"1", "true", "yes"}:
        print("Set BROWSER_USE_RUN_SMOKE=1 to run scenario-managed lifecycle smoke test.")
        return

    scenario = answer(
        url="https://example.com",
        prompt="Open https://example.com and report the title.",
        expected=None,
    )
    setup_prompt = await scenario.__anext__()
    print("Scenario setup prompt length:", len(str(setup_prompt)))

    nav = await env.call_tool("navigate", url="https://example.com", new_tab=False)
    print("Navigate:", nav)

    find = await env.call_tool("find_text", text="Example Domain")
    print("Find text:", find)

    reward = await scenario.asend("Smoke test complete.")
    print("Scenario reward:", reward)


if __name__ == "__main__":
    asyncio.run(main())
