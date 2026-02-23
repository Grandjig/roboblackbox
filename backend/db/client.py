import logging
from datetime import datetime
from typing import Optional, List, Dict
import uuid

log = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.sessions = {}
        self.telemetry = {}
        self.failures = []
    
    async def connect(self):
        log.info("Using in-memory database")
    
    async def disconnect(self):
        pass
    
    async def create_session(self, session_id: str, robot_id: str, metadata: dict) -> dict:
        s = {"id": session_id, "robot_id": robot_id, "started_at": datetime.utcnow().isoformat(), "metadata": metadata}
        self.sessions[session_id] = s
        return s
    
    async def end_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id]["ended_at"] = datetime.utcnow().isoformat()
    
    async def get_sessions(self, robot_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        sessions = list(self.sessions.values())
        if robot_id:
            sessions = [s for s in sessions if s.get("robot_id") == robot_id]
        for s in sessions:
            s["failure_count"] = len([f for f in self.failures if f.get("session_id") == s["id"]])
        return sessions[:limit]
    
    async def insert_telemetry(self, session_id: str, robot_id: str, timestamp, data: dict):
        if session_id not in self.telemetry:
            self.telemetry[session_id] = []
        self.telemetry[session_id].append({
            "time": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
            "model_confidence": data.get("model", {}).get("action_confidence"),
            "task_phase": data.get("task", {}).get("phase"),
            "battery_percent": data.get("system", {}).get("battery_percent"),
        })
        self.telemetry[session_id] = self.telemetry[session_id][-1000:]
    
    async def get_session_telemetry(self, session_id: str, limit: int = 10000) -> List[dict]:
        return self.telemetry.get(session_id, [])[:limit]
    
    async def insert_failure(self, failure: dict) -> dict:
        failure["id"] = str(uuid.uuid4())
        self.failures.insert(0, failure)
        self.failures = self.failures[:100]
        return failure
    
    async def get_failures(self, robot_id: Optional[str] = None, limit: int = 100) -> List[dict]:
        failures = self.failures
        if robot_id:
            failures = [f for f in failures if f.get("robot_id") == robot_id]
        return failures[:limit]

db = Database()
