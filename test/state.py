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

def goal_satisfied(state: AgentState) -> bool:
    if state.step == 0:
        return False
    if goal_requires_environment(state.goal):
        return state.last_result is not None
    return state.last_result is not None
