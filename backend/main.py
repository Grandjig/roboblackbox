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
