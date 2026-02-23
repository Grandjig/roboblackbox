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
