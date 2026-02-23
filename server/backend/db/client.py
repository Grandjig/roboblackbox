"""Database client for TimescaleDB"""

import os
import uuid
import asyncpg
import logging
from datetime import datetime
from typing import Optional, List

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:robotblackbox@localhost:5433/robotblackbox"
)


class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        log.info("Database connected")
    
    async def disconnect(self):
        if self.pool:
            await self.pool.close()
    
    async def create_session(self, session_id: str, robot_id: str, metadata: dict) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO sessions (id, robot_id, started_at, metadata) VALUES ($1, $2, NOW(), $3) RETURNING *",
                uuid.UUID(session_id), robot_id, metadata
            )
            return dict(row)
    
    async def end_session(self, session_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE sessions SET ended_at = NOW() WHERE id = $1", uuid.UUID(session_id))
    
    async def get_sessions(self, robot_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        async with self.pool.acquire() as conn:
            if robot_id:
                rows = await conn.fetch(
                    "SELECT s.*, COUNT(f.id) as failure_count FROM sessions s LEFT JOIN failures f ON f.session_id = s.id WHERE s.robot_id = $1 GROUP BY s.id ORDER BY s.started_at DESC LIMIT $2",
                    robot_id, limit
                )
            else:
                rows = await conn.fetch(
                    "SELECT s.*, COUNT(f.id) as failure_count FROM sessions s LEFT JOIN failures f ON f.session_id = s.id GROUP BY s.id ORDER BY s.started_at DESC LIMIT $1",
                    limit
                )
            return [dict(r) for r in rows]
    
    async def insert_telemetry(self, session_id: str, robot_id: str, timestamp: datetime, data: dict):
        joints = data.get("joints", {})
        gripper = data.get("gripper", {})
        task = data.get("task", {})
        model = data.get("model", {})
        system = data.get("system", {})
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO telemetry (
                    time, session_id, robot_id,
                    joint_positions, joint_velocities, joint_torques, joint_temps,
                    gripper_position, gripper_force, gripper_contact,
                    task_name, task_phase, task_progress,
                    model_confidence, model_uncertainty, model_inference_ms, model_action,
                    cpu_percent, memory_mb, battery_percent, raw_data
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
            """,
                timestamp, uuid.UUID(session_id), robot_id,
                joints.get("positions_rad"), joints.get("velocities_rad_s"),
                joints.get("torques_nm"), joints.get("temperatures_c"),
                gripper.get("position_mm"), gripper.get("force_n"), gripper.get("contact_detected"),
                task.get("current_task"), task.get("phase"), task.get("phase_progress"),
                model.get("action_confidence"), model.get("uncertainty"),
                model.get("inference_time_ms"), model.get("predicted_action"),
                system.get("cpu_percent"), system.get("memory_mb"), system.get("battery_percent"),
                data
            )
    
    async def get_session_telemetry(self, session_id: str, limit: int = 10000) -> List[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT time, model_confidence, task_phase, battery_percent FROM telemetry WHERE session_id = $1 ORDER BY time ASC LIMIT $2",
                uuid.UUID(session_id), limit
            )
            return [dict(r) for r in rows]
    
    async def insert_failure(self, failure: dict) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO failures (session_id, robot_id, detected_at, failure_type, severity, confidence, summary, detail, affected_components, classifier_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING *
            """,
                uuid.UUID(failure["session_id"]), failure["robot_id"],
                failure.get("detected_at", datetime.utcnow()),
                failure["failure_type"], failure["severity"], failure.get("confidence"),
                failure["summary"], failure.get("detail"),
                failure.get("affected_components"), failure.get("classifier_data")
            )
            return dict(row)
    
    async def get_failures(self, robot_id: Optional[str] = None, limit: int = 100) -> List[dict]:
        async with self.pool.acquire() as conn:
            if robot_id:
                rows = await conn.fetch(
                    "SELECT * FROM failures WHERE robot_id = $1 ORDER BY detected_at DESC LIMIT $2",
                    robot_id, limit
                )
            else:
                rows = await conn.fetch("SELECT * FROM failures ORDER BY detected_at DESC LIMIT $1", limit)
            return [dict(r) for r in rows]


db = Database()
