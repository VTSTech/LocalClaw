from dataclasses import dataclass, field

@dataclass
class AgentState:
    goal: str
    step: int = 0
    last_result: str | None = None
    files_written: list[str] = field(default_factory=list)
    completed: bool = False
    collected: dict = field(default_factory=lambda: {
        "environment": False,
        "time": False,
    })

def goal_requires_environment(goal: str) -> bool:
    keywords = [
        "environment", "os", "operating system",
        "system", "platform", "kernel", "distro"
    ]
    g = goal.lower()
    return any(k in g for k in keywords)

def goal_satisfied(state: AgentState) -> bool:
    if goal_requires_environment(state.goal):
        return state.collected["environment"]
    return True
