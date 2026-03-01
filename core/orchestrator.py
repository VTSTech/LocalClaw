"""
LocalClaw — Orchestrator
Coordinates multiple agents via a router agent or explicit hand-off rules.

Two modes:
  1. Router mode  — a lightweight LLM decides which agent to call.
  2. Pipeline mode — agents run sequentially, each receiving the previous output.
  3. Parallel mode — agents run concurrently, results are merged.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Literal

from .agent import Agent, AgentRun
from .ollama_client import OllamaClient


# ------------------------------------------------------------------ #
#  Hand-off & routing                                                  #
# ------------------------------------------------------------------ #

@dataclass
class AgentCard:
    """Describes an agent to the router."""
    name: str
    agent: Agent
    description: str


@dataclass
class OrchestratorResult:
    chosen_agent: str
    runs: dict[str, AgentRun] = field(default_factory=dict)
    final_answer: str = ""
    total_ms: float = 0.0


# ------------------------------------------------------------------ #
#  Orchestrator                                                         #
# ------------------------------------------------------------------ #

class Orchestrator:
    """
    Routes user requests to specialist agents.

    Example
    -------
    orch = Orchestrator(
        agents=[
            AgentCard("coder",  coder_agent,  "Writes and explains code"),
            AgentCard("writer", writer_agent, "Drafts documents and emails"),
        ],
        router_model="llama3.2:3b",
    )
    result = orch.run("Write a Python function to sort a list")
    print(result.final_answer)
    """

    def __init__(
        self,
        agents: list[AgentCard],
        router_model: str | None = None,
        client: OllamaClient | None = None,
        mode: Literal["router", "pipeline", "parallel"] = "router",
    ):
        self.agents = {card.name: card for card in agents}
        self.router_model = router_model or next(iter(self.agents.values())).agent.model
        self.client = client or OllamaClient()
        self.mode = mode

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def run(self, user_input: str) -> OrchestratorResult:
        t0 = time.perf_counter()
        result = OrchestratorResult(chosen_agent="")

        if self.mode == "router":
            result = self._run_router(user_input)
        elif self.mode == "pipeline":
            result = self._run_pipeline(user_input)
        elif self.mode == "parallel":
            result = self._run_parallel(user_input)

        result.total_ms = (time.perf_counter() - t0) * 1000
        return result

    # ------------------------------------------------------------------ #
    #  Router mode                                                         #
    # ------------------------------------------------------------------ #

    def _run_router(self, user_input: str) -> OrchestratorResult:
        chosen = self._route(user_input)
        result = OrchestratorResult(chosen_agent=chosen)

        if chosen not in self.agents:
            # Fallback: use the first agent
            chosen = next(iter(self.agents))

        agent_run = self.agents[chosen].agent.run(user_input)
        result.runs[chosen] = agent_run
        result.final_answer = agent_run.final_answer
        return result

    def _route(self, user_input: str) -> str:
        descriptions = "\n".join(
            f'- "{name}": {card.description}'
            for name, card in self.agents.items()
        )
        names_list = list(self.agents.keys())

        prompt = (
            f"You are a routing assistant. Given the user message below, "
            f"respond with ONLY the name of the best agent from this list: {names_list}.\n\n"
            f"Agents:\n{descriptions}\n\n"
            f"User message: {user_input}\n\n"
            f"Respond with exactly one agent name and nothing else."
        )
        response = self.client.chat(
            model=self.router_model,
            messages=[{"role": "user", "content": prompt}],
        )
        chosen = response.get("message", {}).get("content", "").strip().strip('"').strip("'")

        # Fuzzy match if the model added extra text
        for name in self.agents:
            if name.lower() in chosen.lower():
                return name

        return next(iter(self.agents))  # fallback

    # ------------------------------------------------------------------ #
    #  Pipeline mode                                                       #
    # ------------------------------------------------------------------ #

    def _run_pipeline(self, user_input: str) -> OrchestratorResult:
        result = OrchestratorResult(chosen_agent="pipeline")
        current_input = user_input

        for name, card in self.agents.items():
            run = card.agent.run(current_input)
            result.runs[name] = run
            current_input = run.final_answer  # pipe output to next agent

        result.final_answer = current_input
        return result

    # ------------------------------------------------------------------ #
    #  Parallel mode                                                       #
    # ------------------------------------------------------------------ #

    def _run_parallel(self, user_input: str) -> OrchestratorResult:
        result = OrchestratorResult(chosen_agent="parallel")
        futures = {}

        with ThreadPoolExecutor() as pool:
            for name, card in self.agents.items():
                futures[pool.submit(card.agent.run, user_input)] = name

            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    result.runs[name] = fut.result()
                except Exception as e:
                    from .agent import AgentRun
                    result.runs[name] = AgentRun(success=False, error=str(e))

        # Merge: concatenate all answers with attribution
        parts = []
        for name, run in result.runs.items():
            parts.append(f"[{name}]: {run.final_answer}")
        result.final_answer = "\n\n".join(parts)
        return result
