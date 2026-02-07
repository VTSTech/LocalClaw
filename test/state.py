from dataclasses import dataclass, field

@dataclass
class AgentState:
    goal: str
    step: int = 0
    last_result: str | None = None
    completed: bool = False
    files_written: list[str] = field(default_factory=list)
    # The Plan: A list of discrete tasks for the Worker
    plan: list[str] = field(default_factory=list) 
    collected: dict = field(default_factory=lambda: {
        "environment": False,
        "time": False,
    })

def goal_satisfied(state: AgentState) -> bool:
    if state.step == 0 or state.last_result is None:
        return False
    if "Error:" in state.last_result or "Safety Violation" in state.last_result:
        return False
    # Satisfied if the plan is empty and the last action didn't error
    return len(state.plan) == 0