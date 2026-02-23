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
