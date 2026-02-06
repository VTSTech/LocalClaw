from dataclasses import dataclass, field

@dataclass
class AgentState:
    goal: str
    step: int = 0
    last_result: str | None = None
    completed: bool = False
    files_written: list[str] = field(default_factory=list)
    collected: dict = field(default_factory=lambda: {
        "environment": False,
        "time": False,
    })

def goal_requires_environment(goal: str) -> bool:
    g = goal.lower()
    return any(k in g for k in [
        "dir", "directory", "path",
        "os", "system", "environment",
        "platform", "kernel", "pwd"
    ])

def goal_satisfied(state) -> bool:
    if state.step == 0 or state.last_result is None:
        return False
    # If the tool returned an error, the goal is NOT satisfied
    if "Error:" in state.last_result or "Safety Violation" in state.last_result:
        return False
    return True