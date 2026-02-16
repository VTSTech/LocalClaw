from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class AgentState:
    """
    State management for VTSBot R7.
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
            "result": result[:500],
            "success": success
        })
        self.metrics["total_commands"] += 1
        if not success:
            self.metrics["failed_commands"] += 1