from dataclasses import dataclass, field

@dataclass
class AgentState:
    goal: str
    step: int = 0
    last_result: str | None = None
    completed: bool = False
    files_written: list[str] = field(default_factory=list)
    # The Plan: A list of tasks for the Worker
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
    # Goal is satisfied only when the plan is empty
    return len(state.plan) == 0