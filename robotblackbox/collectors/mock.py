"""Mock Collector - simulates robot telemetry for testing"""

import random
import math
import asyncio
from datetime import datetime


class MockCollector:
    """
    Simulates a 6-DOF robot arm with intentional failure injection.
    Use this to test without actual hardware.
    """
    
    def __init__(self, robot_id: str):
        self.robot_id = robot_id
        self.t = 0
        self.failure_countdown = random.randint(50, 200)
        self.active_failure = "none"
        self.failure_duration = 0
        self.joint_positions = [0.0] * 6
        self.joint_velocities = [0.0] * 6
        self.joint_torques = [0.0] * 6
    
    async def get_state(self) -> dict:
        self.t += 1
        await asyncio.sleep(0)
        
        self._tick_failure()
        self._update_joints()
        
        return {
            "joints": self._get_joint_data(),
            "gripper": self._get_gripper_data(),
            "task": self._get_task_data(),
            "model": self._get_model_data(),
            "system": self._get_system_data(),
        }
    
    def _tick_failure(self):
        if self.active_failure != "none":
            self.failure_duration -= 1
            if self.failure_duration <= 0:
                self.active_failure = "none"
                self.failure_countdown = random.randint(50, 200)
        else:
            self.failure_countdown -= 1
            if self.failure_countdown <= 0:
                self.active_failure = random.choice([
                    "sensor_dropout", "motor_overload", "model_low_confidence"
                ])
                self.failure_duration = random.randint(5, 20)
    
    def _update_joints(self):
        for i in range(6):
            freq = 0.01 * (i + 1)
            self.joint_positions[i] = math.sin(self.t * freq) * math.pi / 4
            self.joint_velocities[i] = math.cos(self.t * freq) * freq * math.pi / 4
            self.joint_torques[i] = abs(self.joint_velocities[i]) * 10 + random.gauss(0, 0.5)
    
    def _get_joint_data(self) -> dict:
        positions = list(self.joint_positions)
        velocities = list(self.joint_velocities)
        torques = list(self.joint_torques)
        
        if self.active_failure == "sensor_dropout":
            idx = random.randint(0, 5)
            positions[idx] = None
            velocities[idx] = None
        
        if self.active_failure == "motor_overload":
            idx = random.randint(0, 5)
            torques[idx] = torques[idx] * 8 + random.uniform(50, 100)
        
        return {
            "positions_rad": positions,
            "velocities_rad_s": velocities,
            "torques_nm": torques,
            "temperatures_c": [35 + random.gauss(0, 2) for _ in range(6)],
        }
    
    def _get_gripper_data(self) -> dict:
        return {
            "position_mm": 50 + math.sin(self.t * 0.02) * 30,
            "force_n": abs(random.gauss(5, 1)),
            "contact_detected": random.random() > 0.7,
        }
    
    def _get_task_data(self) -> dict:
        phases = ["reaching", "grasping", "lifting", "placing", "returning"]
        return {
            "current_task": "pick_and_place",
            "phase": phases[(self.t // 30) % len(phases)],
            "phase_progress": (self.t % 30) / 30.0,
        }
    
    def _get_model_data(self) -> dict:
        confidence = random.uniform(0.75, 0.99)
        if self.active_failure == "model_low_confidence":
            confidence = random.uniform(0.15, 0.40)
        return {
            "action_confidence": confidence,
            "inference_time_ms": random.uniform(80, 120),
            "predicted_action": "move_to_target",
            "uncertainty": 1.0 - confidence,
        }
    
    def _get_system_data(self) -> dict:
        return {
            "timestamp_robot": datetime.utcnow().isoformat() + "Z",
            "cpu_percent": random.uniform(45, 75),
            "memory_mb": random.uniform(800, 1200),
            "battery_percent": max(0, 100 - (self.t * 0.01)),
        }
