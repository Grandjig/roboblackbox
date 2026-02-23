"""RobotBlackBox Agent - runs on the robot, streams telemetry to server"""

import asyncio
import json
import uuid
import logging
import platform
from datetime import datetime
from typing import Optional
from pathlib import Path

import websockets
import psutil

from robotblackbox.config import Config

log = logging.getLogger("robotblackbox")


class BlackBoxAgent:
    """
    The core agent - runs on your robot.
    
    Collects telemetry from ROS2 (or mock), streams to server.
    Buffers locally if connection drops.
    
    Usage:
        agent = BlackBoxAgent(config)
        await agent.run()
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.session_id = str(uuid.uuid4())
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.buffer = []
        self.collector = None
        
        # Ensure local cache dir exists
        self.config.local_cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_collector(self):
        """Initialize the appropriate data collector"""
        if self.config.use_mock:
            from robotblackbox.collectors.mock import MockCollector
            log.info("Using MOCK collector (no ROS2)")
            return MockCollector(self.config.robot_id)
        
        try:
            from robotblackbox.collectors.ros2 import ROS2Collector
            log.info("Using ROS2 collector")
            return ROS2Collector(
                robot_id=self.config.robot_id,
                joint_states_topic=self.config.ros2_joint_states_topic,
                task_status_topic=self.config.ros2_task_status_topic,
                model_confidence_topic=self.config.ros2_model_confidence_topic,
            )
        except ImportError:
            log.warning("ROS2 not available, falling back to mock collector")
            from robotblackbox.collectors.mock import MockCollector
            return MockCollector(self.config.robot_id)
    
    async def connect(self):
        """Connect to server with auto-retry"""
        while self.running:
            try:
                url = f"{self.config.server_url}/ws/agent/{self.config.robot_id}"
                log.info(f"Connecting to {url}...")
                
                self.ws = await websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                )
                log.info(f"Connected! Session: {self.session_id}")
                
                # Send session start
                await self._send({
                    "type": "session_start",
                    "session_id": self.session_id,
                    "robot_id": self.config.robot_id,
                    "timestamp": self._now(),
                    "metadata": {
                        "agent_version": "0.1.0",
                        "hostname": platform.node(),
                        "platform": platform.system(),
                        "share_failures": self.config.share_anonymized_failures,
                    }
                })
                
                # Flush buffered events
                await self._flush_buffer()
                return True
                
            except Exception as e:
                log.warning(f"Connection failed: {e}. Retrying in 5s...")
                self.ws = None
                await asyncio.sleep(5)
    
    async def _send(self, event: dict):
        """Send event to server, buffer if disconnected"""
        if self.ws and self.ws.open:
            try:
                await self.ws.send(json.dumps(event))
                return
            except Exception as e:
                log.warning(f"Send failed: {e}")
                self.ws = None
        
        # Buffer locally
        if len(self.buffer) < self.config.buffer_max:
            self.buffer.append(event)
    
    async def _flush_buffer(self):
        """Send buffered events when reconnected"""
        if self.buffer and self.ws:
            log.info(f"Flushing {len(self.buffer)} buffered events...")
            for event in self.buffer:
                await self.ws.send(json.dumps(event))
            self.buffer.clear()
    
    async def _collect_loop(self):
        """Main collection loop"""
        interval = 1.0 / self.config.collection_hz
        log.info(f"Starting collection at {self.config.collection_hz}Hz...")
        
        while self.running:
            try:
                state = await self.collector.get_state()
                
                await self._send({
                    "type": "telemetry",
                    "session_id": self.session_id,
                    "robot_id": self.config.robot_id,
                    "timestamp": self._now(),
                    "data": state,
                })
                
            except Exception as e:
                await self._send({
                    "type": "error",
                    "session_id": self.session_id,
                    "robot_id": self.config.robot_id,
                    "timestamp": self._now(),
                    "data": {"error_type": type(e).__name__, "error_msg": str(e)}
                })
            
            await asyncio.sleep(interval)
    
    async def _heartbeat_loop(self):
        """Send heartbeat every 5s"""
        while self.running:
            await self._send({
                "type": "heartbeat",
                "session_id": self.session_id,
                "robot_id": self.config.robot_id,
                "timestamp": self._now(),
                "data": {
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "buffer_size": len(self.buffer),
                }
            })
            await asyncio.sleep(5)
    
    async def _reconnect_loop(self):
        """Monitor connection and reconnect if needed"""
        while self.running:
            if self.ws is None or not self.ws.open:
                await self.connect()
            await asyncio.sleep(1)
    
    async def run(self):
        """Start the agent"""
        self.running = True
        self.collector = self._init_collector()
        
        log.info(f"RobotBlackBox Agent starting")
        log.info(f"  Robot ID: {self.config.robot_id}")
        log.info(f"  Server: {self.config.server_url}")
        log.info(f"  Session: {self.session_id}")
        
        await asyncio.gather(
            self._reconnect_loop(),
            self._collect_loop(),
            self._heartbeat_loop(),
        )
    
    async def stop(self):
        """Stop the agent gracefully"""
        self.running = False
        if self.ws:
            await self.ws.close()
    
    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"
