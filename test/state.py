from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class AgentState:
    """
    Enhanced state management for VTSBot R3.
    """
    goal: str
    step: int = 0
    last_result: Optional[str] = None
    completed: bool = False
    retries: int = 0
    files_written: List[str] = field(default_factory=list)
    commands_executed: List[Dict] = field(default_factory=list)
    
    # Agent performance tracking
    active_agent: str = "Dispatcher"
    agent_transitions: List[Dict] = field(default_factory=list)
    
    # Metadata collection
    collected: Dict = field(default_factory=lambda: {
        "environment": False,
        "system_info": {},
        "start_time": datetime.now().isoformat(),
        "session_id": None,
    })
    
    # Performance metrics
    metrics: Dict = field(default_factory=lambda: {
        "total_commands": 0,
        "failed_commands": 0,
        "auditor_passes": 0,
        "auditor_fails": 0,
        "retry_events": 0,
    })
    
    def add_command(self, command: str, tag: str, result: str, success: bool = True):
        """Record executed command"""
        self.commands_executed.append({
            "step": self.step,
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "tag": tag,
            "result": result[:500],  # Truncate long outputs
            "success": success
        })
        self.metrics["total_commands"] += 1
        if not success:
            self.metrics["failed_commands"] += 1
    
    def agent_transition(self, from_agent: str, to_agent: str, reason: str = ""):
        """Track agent handoffs"""
        self.agent_transitions.append({
            "timestamp": datetime.now().isoformat(),
            "from": from_agent,
            "to": to_agent,
            "reason": reason,
            "step": self.step
        })
    
    def get_session_summary(self) -> Dict:
        """Get session summary for reporting"""
        return {
            "session_id": self.collected.get("session_id"),
            "duration": str(datetime.now() - datetime.fromisoformat(self.collected["start_time"])),
            "steps": self.step,
            "commands_executed": len(self.commands_executed),
            "files_created": len(self.files_written),
            "metrics": self.metrics,
            "last_result": self.last_result[:200] if self.last_result else None,
        }

def goal_satisfied(state: AgentState) -> bool:
    """
    Enhanced goal satisfaction check with more indicators.
    """
    if state.step == 0 or state.last_result is None:
        return False
    
    # Success indicators
    success_indicators = [
        "SUCCESS",
        "completed",
        "finished",
        "done",
        "created",
        "copied",
        "moved",
        "verified",
        "found",
    ]
    
    # Failure indicators (more comprehensive)
    failure_indicators = [
        "Error:", "error:", "ERROR:",
        "Safety Violation",
        "not found", "cannot stat", "No such",
        "Permission denied", "permission denied",
        "command not found",
        "failed", "Failed", "FAILED",
        "timed out",
        "invalid", "Invalid",
        "refused", "Refused",
        "missing", "Missing",
    ]
    
    result_lower = state.last_result.lower()
    
    # Check for failures
    if any(indicator.lower() in result_lower for indicator in failure_indicators):
        return False
    
    # For certain operations, check for success indicators
    if state.step > 1:  # Not the first step
        if any(indicator in result_lower for indicator in success_indicators):
            return True
    
    # Default: assume success if no failure indicators
    return not any(failure.lower() in result_lower for failure in failure_indicators)