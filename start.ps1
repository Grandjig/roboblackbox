# RobotBlackBox - Complete Auto-Setup
# Run: .\start.ps1

$ErrorActionPreference = "Continue"
$ROOT = $PSScriptRoot
if (-not $ROOT) { $ROOT = Get-Location }

Write-Host "`n=== RobotBlackBox Setup ===" -ForegroundColor Cyan

# Kill old processes
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}

# ===========================================
# CREATE ALL MISSING FILES
# ===========================================
Write-Host "Creating missing files..." -ForegroundColor Yellow

# Backend directories
New-Item -ItemType Directory -Path "$ROOT\backend\db" -Force | Out-Null
New-Item -ItemType Directory -Path "$ROOT\backend\classifier" -Force | Out-Null
New-Item -ItemType Directory -Path "$ROOT\agent\collectors" -Force | Out-Null

# __init__.py files
"" | Out-File -FilePath "$ROOT\backend\db\__init__.py" -Encoding UTF8
"" | Out-File -FilePath "$ROOT\backend\classifier\__init__.py" -Encoding UTF8
"" | Out-File -FilePath "$ROOT\agent\collectors\__init__.py" -Encoding UTF8

# Backend classifier
$classifierCode = @'
import logging
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

@dataclass
class FailureResult:
    is_failure: bool
    failure_type: str
    severity: str
    confidence: float
    summary: str
    detail: str
    affected_components: Dict
    classifier_data: Dict

class RollingStats:
    def __init__(self, window: int = 50):
        self.values = deque(maxlen=window)
    
    def update(self, value):
        if value is not None:
            self.values.append(value)
    
    @property
    def mean(self):
        return sum(self.values) / len(self.values) if self.values else None
    
    @property
    def std(self):
        if len(self.values) < 2:
            return None
        m = self.mean
        return (sum((x - m) ** 2 for x in self.values) / len(self.values)) ** 0.5

class FailureClassifier:
    def __init__(self):
        self._stats = {}
    
    def classify(self, robot_id: str, data: dict) -> FailureResult:
        joints = data.get("joints", {})
        model = data.get("model", {})
        system = data.get("system", {})
        
        # Check sensor dropout
        positions = joints.get("positions_rad", [])
        null_joints = [i for i, p in enumerate(positions) if p is None]
        if null_joints:
            return FailureResult(True, "sensor", "high", 0.95,
                f"Sensor dropout on joints {null_joints}",
                "Encoder returned null. Check connections.",
                {"joints": null_joints}, {})
        
        # Check motor overload
        torques = joints.get("torques_nm", [])
        overload = [i for i, t in enumerate(torques) if t and t > 50]
        if overload:
            return FailureResult(True, "motor", "high", 0.90,
                f"Motor overload on joints {overload}",
                "High torque detected. Check for obstruction.",
                {"joints": overload}, {})
        
        # Check model confidence
        conf = model.get("action_confidence")
        if conf is not None:
            if conf < 0.25:
                return FailureResult(True, "model", "critical", 0.88,
                    f"AI critically uncertain ({conf:.0%})",
                    "Model in unfamiliar situation.",
                    {"confidence": conf}, {})
            if conf < 0.45:
                return FailureResult(True, "model", "medium", 0.80,
                    f"AI low confidence ({conf:.0%})",
                    "Model uncertain. Monitor closely.",
                    {"confidence": conf}, {})
        
        # Check battery
        battery = system.get("battery_percent")
        if battery is not None and battery < 15:
            return FailureResult(True, "system", "medium", 1.0,
                f"Low battery ({battery:.0f}%)",
                "Return to charging station.",
                {"battery": battery}, {})
        
        return FailureResult(False, "none", "none", 1.0, "OK", "", {}, {})

classifier = FailureClassifier()
'@
$classifierCode | Out-File -FilePath "$ROOT\backend\classifier\classifier.py" -Encoding UTF8

# Backend db client (memory-only, no real DB needed)
$dbClientCode = @'
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
'@
$dbClientCode | Out-File -FilePath "$ROOT\backend\db\client.py" -Encoding UTF8

# Backend main.py
$backendCode = @'
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Set, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from db.client import db
from classifier.classifier import classifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SERVER] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="RobotBlackBox")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

dashboard_connections: Dict[str, Set[WebSocket]] = {}

@app.on_event("startup")
async def startup():
    await db.connect()
    log.info("Server ready on http://localhost:8000")

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws/agent/{robot_id}")
async def agent_ws(websocket: WebSocket, robot_id: str):
    await websocket.accept()
    log.info(f"Agent connected: {robot_id}")
    session_id = None
    
    try:
        async for raw in websocket.iter_text():
            try:
                event = json.loads(raw)
                etype = event.get("type")
                
                if etype == "session_start":
                    session_id = event.get("session_id", str(uuid.uuid4()))
                    await db.create_session(session_id, robot_id, event.get("metadata", {}))
                    log.info(f"Session: {session_id}")
                
                elif etype == "telemetry" and session_id:
                    ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                    data = event.get("data", {})
                    await db.insert_telemetry(session_id, robot_id, ts, data)
                    
                    result = classifier.classify(robot_id, data)
                    if result.is_failure:
                        log.warning(f"[{robot_id}] {result.failure_type}: {result.summary}")
                        f = await db.insert_failure({
                            "session_id": session_id,
                            "robot_id": robot_id,
                            "detected_at": ts.isoformat(),
                            "failure_type": result.failure_type,
                            "severity": result.severity,
                            "summary": result.summary,
                        })
                        await broadcast(robot_id, {"type": "failure", "robot_id": robot_id, "failure": f})
                    
                    await broadcast(robot_id, {
                        "type": "telemetry",
                        "robot_id": robot_id,
                        "timestamp": ts.isoformat(),
                        "model_confidence": data.get("model", {}).get("action_confidence"),
                        "battery_percent": data.get("system", {}).get("battery_percent"),
                        "task_phase": data.get("task", {}).get("phase"),
                    })
            except Exception as e:
                log.error(f"Error: {e}")
    except WebSocketDisconnect:
        log.info(f"Agent disconnected: {robot_id}")
    finally:
        if session_id:
            await db.end_session(session_id)

@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await websocket.accept()
    log.info("Dashboard connected")
    subs = set()
    try:
        async for raw in websocket.iter_text():
            msg = json.loads(raw)
            if msg.get("type") == "subscribe":
                rid = msg.get("robot_id")
                if rid:
                    subs.add(rid)
                    if rid not in dashboard_connections:
                        dashboard_connections[rid] = set()
                    dashboard_connections[rid].add(websocket)
                    await websocket.send_text(json.dumps({"type": "subscribed", "robot_id": rid}))
    except WebSocketDisconnect:
        pass
    finally:
        for rid in subs:
            if rid in dashboard_connections:
                dashboard_connections[rid].discard(websocket)

async def broadcast(robot_id: str, msg: dict):
    conns = dashboard_connections.get(robot_id, set())
    dead = set()
    for ws in conns:
        try:
            await ws.send_text(json.dumps(msg))
        except:
            dead.add(ws)
    for ws in dead:
        conns.discard(ws)

@app.get("/api/sessions")
async def get_sessions(robot_id: Optional[str] = None):
    return {"sessions": await db.get_sessions(robot_id)}

@app.get("/api/sessions/{session_id}/telemetry")
async def get_telemetry(session_id: str):
    return {"telemetry": await db.get_session_telemetry(session_id)}

@app.get("/api/failures")
async def get_failures(robot_id: Optional[str] = None):
    return {"failures": await db.get_failures(robot_id)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'@
$backendCode | Out-File -FilePath "$ROOT\backend\main.py" -Encoding UTF8

# Agent mock collector
$mockCode = @'
import random
import math
import asyncio
from datetime import datetime

class MockCollector:
    def __init__(self, robot_id: str):
        self.robot_id = robot_id
        self.t = 0
        self.failure_countdown = random.randint(50, 200)
        self.active_failure = "none"
        self.failure_duration = 0
    
    async def get_state(self) -> dict:
        self.t += 1
        await asyncio.sleep(0)
        
        if self.active_failure != "none":
            self.failure_duration -= 1
            if self.failure_duration <= 0:
                self.active_failure = "none"
                self.failure_countdown = random.randint(50, 200)
        else:
            self.failure_countdown -= 1
            if self.failure_countdown <= 0:
                self.active_failure = random.choice(["sensor_dropout", "motor_overload", "model_low_confidence"])
                self.failure_duration = random.randint(5, 20)
        
        positions = [math.sin(self.t * 0.01 * (i+1)) * 0.5 for i in range(6)]
        velocities = [math.cos(self.t * 0.01 * (i+1)) * 0.1 for i in range(6)]
        torques = [abs(v) * 10 + random.gauss(0, 0.5) for v in velocities]
        
        if self.active_failure == "sensor_dropout":
            idx = random.randint(0, 5)
            positions[idx] = None
            velocities[idx] = None
        
        if self.active_failure == "motor_overload":
            idx = random.randint(0, 5)
            torques[idx] = torques[idx] * 8 + random.uniform(50, 100)
        
        confidence = random.uniform(0.75, 0.99)
        if self.active_failure == "model_low_confidence":
            confidence = random.uniform(0.15, 0.40)
        
        return {
            "joints": {"positions_rad": positions, "velocities_rad_s": velocities, "torques_nm": torques, "temperatures_c": [35 + random.gauss(0, 2) for _ in range(6)]},
            "gripper": {"position_mm": 50, "force_n": 5, "contact_detected": False},
            "task": {"current_task": "pick_and_place", "phase": ["reaching", "grasping", "lifting", "placing", "returning"][(self.t // 30) % 5], "phase_progress": (self.t % 30) / 30.0},
            "model": {"action_confidence": confidence, "inference_time_ms": random.uniform(80, 120), "predicted_action": "move", "uncertainty": 1 - confidence},
            "system": {"timestamp_robot": datetime.utcnow().isoformat() + "Z", "cpu_percent": random.uniform(45, 75), "memory_mb": random.uniform(800, 1200), "battery_percent": max(0, 100 - (self.t * 0.01))},
        }
'@
$mockCode | Out-File -FilePath "$ROOT\agent\collectors\mock.py" -Encoding UTF8

# Agent main
$agentCode = @'
import asyncio
import json
import argparse
import logging
import uuid
import platform
from datetime import datetime

import websockets
import psutil

from collectors.mock import MockCollector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [AGENT] %(message)s")
log = logging.getLogger(__name__)

class Agent:
    def __init__(self, robot_id: str, backend_url: str, use_mock: bool = True):
        self.robot_id = robot_id
        self.backend_url = backend_url
        self.session_id = str(uuid.uuid4())
        self.ws = None
        self.running = False
        self.collector = MockCollector(robot_id) if use_mock else None
    
    async def connect(self):
        while self.running:
            try:
                url = f"{self.backend_url}/ws/agent/{self.robot_id}"
                log.info(f"Connecting to {url}...")
                self.ws = await websockets.connect(url, ping_interval=20, ping_timeout=10)
                log.info(f"Connected! Session: {self.session_id}")
                
                await self.ws.send(json.dumps({
                    "type": "session_start",
                    "session_id": self.session_id,
                    "robot_id": self.robot_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "metadata": {"hostname": platform.node()}
                }))
                return True
            except Exception as e:
                log.warning(f"Connection failed: {e}. Retrying in 5s...")
                self.ws = None
                await asyncio.sleep(5)
    
    async def send(self, event: dict):
        if self.ws:
            try:
                await self.ws.send(json.dumps(event))
            except:
                self.ws = None
    
    async def collect_loop(self):
        while self.running:
            try:
                state = await self.collector.get_state()
                await self.send({
                    "type": "telemetry",
                    "session_id": self.session_id,
                    "robot_id": self.robot_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "data": state,
                })
            except Exception as e:
                log.error(f"Collect error: {e}")
            await asyncio.sleep(0.1)
    
    async def reconnect_loop(self):
        while self.running:
            if self.ws is None:
                await self.connect()
            await asyncio.sleep(1)
    
    async def run(self):
        self.running = True
        log.info(f"Starting agent: {self.robot_id}")
        await asyncio.gather(self.reconnect_loop(), self.collect_loop())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot-id", default="robot_001")
    parser.add_argument("--backend", default="ws://localhost:8000")
    parser.add_argument("--mock", action="store_true", default=True)
    args = parser.parse_args()
    
    agent = Agent(args.robot_id, args.backend, args.mock)
    asyncio.run(agent.run())

if __name__ == "__main__":
    main()
'@
$agentCode | Out-File -FilePath "$ROOT\agent\agent.py" -Encoding UTF8

Write-Host "  Files created!" -ForegroundColor Green

# ===========================================
# START BACKEND
# ===========================================
Write-Host "`n[1/3] Starting Backend..." -ForegroundColor Yellow

$backendScript = @"
cd '$ROOT\backend'
Write-Host 'Installing dependencies...' -ForegroundColor Cyan
pip install fastapi uvicorn websockets psutil --quiet 2>`$null
Write-Host ''
Write-Host '=== BACKEND RUNNING ===' -ForegroundColor Green
Write-Host 'http://localhost:8000' -ForegroundColor White
Write-Host ''
python main.py
Read-Host 'Press Enter'
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendScript
Write-Host "  Backend starting..." -ForegroundColor Green
Start-Sleep -Seconds 5

# ===========================================
# START FRONTEND
# ===========================================
Write-Host "`n[2/3] Starting Frontend..." -ForegroundColor Yellow

$frontendScript = @"
cd '$ROOT\frontend'
Write-Host 'Installing dependencies...' -ForegroundColor Cyan
npm install 2>`$null
Write-Host ''
Write-Host '=== FRONTEND RUNNING ===' -ForegroundColor Green
Write-Host 'http://localhost:3000' -ForegroundColor White
Write-Host ''
npm run dev
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendScript
Write-Host "  Frontend starting..." -ForegroundColor Green
Start-Sleep -Seconds 5

# ===========================================
# START AGENT
# ===========================================
Write-Host "`n[3/3] Starting Mock Agent..." -ForegroundColor Yellow

$agentScript = @"
cd '$ROOT\agent'
Write-Host 'Installing dependencies...' -ForegroundColor Cyan
pip install websockets psutil --quiet 2>`$null
Write-Host ''
Write-Host '=== MOCK AGENT RUNNING ===' -ForegroundColor Green
Write-Host 'Robot: robot_001' -ForegroundColor White
Write-Host ''
python agent.py --mock --robot-id robot_001 --backend ws://localhost:8000
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $agentScript
Write-Host "  Agent starting..." -ForegroundColor Green

# ===========================================
# DONE
# ===========================================
Write-Host "`n=== ALL SYSTEMS LAUNCHED ===" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard: http://localhost:3000" -ForegroundColor White
Write-Host "  Backend:   http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "  Wait 10-15 seconds, then open the dashboard." -ForegroundColor Yellow
Write-Host "  You should see LIVE status and streaming data." -ForegroundColor Yellow
Write-Host ""
Write-Host "  No database needed - runs entirely in memory!" -ForegroundColor Gray
Write-Host ""

Read-Host "Press Enter to close this window"
