"""RobotBlackBox Backend Server"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db.client import db
from classifier.classifier import classifier, FailureResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SERVER] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="RobotBlackBox", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

dashboard_connections: Dict[str, Set[WebSocket]] = {}


@app.on_event("startup")
async def startup():
    await db.connect()
    log.info("RobotBlackBox server started")


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


@app.websocket("/ws/agent/{robot_id}")
async def agent_websocket(websocket: WebSocket, robot_id: str):
    await websocket.accept()
    log.info(f"Agent connected: {robot_id}")
    session_id = None
    
    try:
        async for raw_message in websocket.iter_text():
            try:
                event = json.loads(raw_message)
                event_type = event.get("type")
                
                if event_type == "session_start":
                    session_id = event["session_id"]
                    await db.create_session(session_id, robot_id, event.get("metadata", {}))
                    log.info(f"Session started: {session_id}")
                
                elif event_type == "telemetry" and session_id:
                    ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                    data = event.get("data", {})
                    
                    await db.insert_telemetry(session_id, robot_id, ts, data)
                    
                    result: FailureResult = classifier.classify(robot_id, data)
                    
                    if result.is_failure:
                        log.warning(f"[{robot_id}] FAILURE: {result.failure_type} | {result.summary}")
                        
                        failure_record = await db.insert_failure({
                            "session_id": session_id,
                            "robot_id": robot_id,
                            "detected_at": ts,
                            "failure_type": result.failure_type,
                            "severity": result.severity,
                            "confidence": result.confidence,
                            "summary": result.summary,
                            "detail": result.detail,
                            "affected_components": result.affected_components,
                            "classifier_data": result.classifier_data,
                        })
                        
                        await broadcast_to_dashboards(robot_id, {
                            "type": "failure",
                            "robot_id": robot_id,
                            "failure": {
                                "id": str(failure_record["id"]),
                                "failure_type": result.failure_type,
                                "severity": result.severity,
                                "summary": result.summary,
                                "timestamp": ts.isoformat(),
                            }
                        })
                    
                    await broadcast_to_dashboards(robot_id, {
                        "type": "telemetry",
                        "robot_id": robot_id,
                        "timestamp": ts.isoformat(),
                        "model_confidence": data.get("model", {}).get("action_confidence"),
                        "battery_percent": data.get("system", {}).get("battery_percent"),
                        "task_phase": data.get("task", {}).get("phase"),
                    })
                
                elif event_type == "heartbeat":
                    pass
                    
            except json.JSONDecodeError:
                log.error(f"Invalid JSON from {robot_id}")
            except Exception as e:
                log.error(f"Error processing event: {e}")
    
    except WebSocketDisconnect:
        log.info(f"Agent disconnected: {robot_id}")
    finally:
        if session_id:
            await db.end_session(session_id)


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()
    subscribed_robots = set()
    
    try:
        async for raw in websocket.iter_text():
            msg = json.loads(raw)
            if msg.get("type") == "subscribe":
                robot_id = msg.get("robot_id")
                if robot_id:
                    subscribed_robots.add(robot_id)
                    if robot_id not in dashboard_connections:
                        dashboard_connections[robot_id] = set()
                    dashboard_connections[robot_id].add(websocket)
                    await websocket.send_text(json.dumps({"type": "subscribed", "robot_id": robot_id}))
    except WebSocketDisconnect:
        pass
    finally:
        for robot_id in subscribed_robots:
            if robot_id in dashboard_connections:
                dashboard_connections[robot_id].discard(websocket)


async def broadcast_to_dashboards(robot_id: str, message: dict):
    connections = dashboard_connections.get(robot_id, set())
    if not connections:
        return
    
    dead = set()
    msg_str = json.dumps(message)
    
    for ws in connections:
        try:
            await ws.send_text(msg_str)
        except Exception:
            dead.add(ws)
    
    for ws in dead:
        connections.discard(ws)


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/sessions")
async def list_sessions(robot_id: Optional[str] = None, limit: int = 50):
    sessions = await db.get_sessions(robot_id=robot_id, limit=limit)
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}/telemetry")
async def get_session_telemetry(session_id: str, limit: int = 5000):
    telemetry = await db.get_session_telemetry(session_id, limit=limit)
    return {"session_id": session_id, "telemetry": telemetry}


@app.get("/api/failures")
async def list_failures(robot_id: Optional[str] = None, limit: int = 100):
    failures = await db.get_failures(robot_id=robot_id, limit=limit)
    return {"failures": failures}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
