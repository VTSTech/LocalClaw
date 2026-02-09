from dataclasses import dataclass, field

@dataclass
class AgentState:
    """
    Maintains the state of the VTSBot session.
    Updated for R2 Tag-Based Routing.
    """
    goal: str
    step: int = 0
    last_result: str | None = None
    completed: bool = False
    files_written: list[str] = field(default_factory=list)
    
    # Metadata for local lookups and context synchronization
    collected: dict = field(default_factory=lambda: {
        "environment": False,
        "time": False,
    })

def goal_satisfied(state: AgentState) -> bool:
    """
    Heuristic check to see if the immediate task was successful.
    In R2, this is primarily used for logging and session branching.
    """
    if state.step == 0 or state.last_result is None:
        return False
        
    # Standard Linux error indicators
    failure_indicators = [
        "Error:", 
        "Safety Violation", 
        "not found", 
        "cannot stat", 
        "Permission denied"
    ]
    
    if any(indicator in state.last_result for indicator in failure_indicators):
        return False
        
    # If a result exists and contains no obvious errors, assume success for the step
    return True