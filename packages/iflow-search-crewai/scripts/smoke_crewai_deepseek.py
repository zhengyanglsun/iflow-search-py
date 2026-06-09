#!/usr/bin/env python3
"""Opt-in CrewAI + DeepSeek agent-loop smoke.

Requires:
  IFLOW_CREWAI_AGENT_SMOKE=1
  IFLOW_API_KEY
  DEEPSEEK_API_KEY

Does not print API keys or Authorization headers.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    if os.environ.get("IFLOW_CREWAI_AGENT_SMOKE") != "1":
        print("Refusing to run: set IFLOW_CREWAI_AGENT_SMOKE=1 to opt in.", file=sys.stderr)
        return 2
    if not os.environ.get("IFLOW_API_KEY"):
        print("IFLOW_API_KEY is not set.", file=sys.stderr)
        return 2
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY is not set; skipping agent smoke.", file=sys.stderr)
        return 2

    try:
        from crewai import LLM, Agent, Crew, Task
    except ImportError:
        print("crewai is not installed.", file=sys.stderr)
        return 2

    from iflow_search_crewai import IFlowWebSearchTool

    llm = LLM(model="deepseek/deepseek-chat", api_key=os.environ["DEEPSEEK_API_KEY"])
    researcher = Agent(
        role="Web Researcher",
        goal="Answer with one short sentence using web search",
        backstory="Use iflow_web_search for current facts.",
        tools=[IFlowWebSearchTool()],
        llm=llm,
        verbose=False,
    )
    task = Task(
        description="What is CrewAI? One sentence only.",
        expected_output="One sentence answer.",
        agent=researcher,
    )
    crew = Crew(agents=[researcher], tasks=[task], verbose=False)
    try:
        result = crew.kickoff()
    except Exception as exc:
        print(f"agent_smoke=failed error_type={type(exc).__name__}")
        print(f"hint={str(exc)[:200]}")
        return 1

    text = str(result.raw if hasattr(result, "raw") else result)
    summary = text.replace("\n", " ")[:200]
    print("agent_smoke=ok tool_used=iflow_web_search (expected)")
    print(f"answer_summary={summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
