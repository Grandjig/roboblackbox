"""
ROS2 Collector — real robot data collection
Subscribes to standard ROS2 topics and normalizes them
into the BlackBox schema.

Requires: ros2, rclpy, sensor_msgs, control_msgs
"""

import asyncio
import threading
from typing import Optional
from datetime import datetime


class ROS2Collector:
    """
    Collects data from a real ROS2 robot.
    Subscribes to standard topics:
    - /joint_states (positions, velocities, torques)
    - /gripper/state
    - /robot/task_status  
    - /model/inference_result (custom topic from VLA model)
    
    Run your VLA model separately and have it publish to
    /model/inference_result with confidence scores.
    """
    
    def __init__(self, robot_id: str):
        self.robot_id = robot_id
        self._latest_state = {}
        self._lock = threading.Lock()
        self._initialized = False
        
        # Init ROS2 in a background thread
        self._ros_thread = threading.Thread(target=self._init_ros, daemon=True)
        self._ros_thread.start()

    def _init_ros(self):
        try:
            import rclpy
            from rclpy.node import Node
            from sensor_msgs.msg import JointState
            from std_msgs.msg import String, Float32
            
            rclpy.init()
            
            class BlackBoxNode(Node):
                def __init__(inner_self):
                    super().__init__('blackbox_agent')
                    
                    inner_self.create_subscription(
                        JointState,
                        '/joint_states',
                        lambda msg: self._on_joint_states(msg),
                        10
                    )
                    
                    inner_self.create_subscription(
                        String,
                        '/robot/task_status',
                        lambda msg: self._on_task_status(msg),
                        10
                    )
                    
                    inner_self.create_subscription(
                        Float32,
                        '/model/action_confidence',
                        lambda msg: self._on_model_confidence(msg),
                        10
                    )
            
            node = BlackBoxNode()
            self._initialized = True
            rclpy.spin(node)
            
        except Exception as e:
            print(f"[ROS2Collector] Init failed: {e}")

    def _on_joint_states(self, msg):
        with self._lock:
            self._latest_state["joints"] = {
                "names": list(msg.name),
                "positions_rad": list(msg.position),
                "velocities_rad_s": list(msg.velocity),
                "torques_nm": list(msg.effort),
                "temperatures_c": []  # Not in standard JointState, add your own topic
            }

    def _on_task_status(self, msg):
        with self._lock:
            try:
                import json
                data = json.loads(msg.data)
                self._latest_state["task"] = data
            except Exception:
                self._latest_state["task"] = {"raw": msg.data}

    def _on_model_confidence(self, msg):
        with self._lock:
            if "model" not in self._latest_state:
                self._latest_state["model"] = {}
            self._latest_state["model"]["action_confidence"] = msg.data
            self._latest_state["model"]["uncertainty"] = 1.0 - msg.data

    async def get_state(self) -> dict:
        """Return latest state snapshot"""
        await asyncio.sleep(0)
        with self._lock:
            state = dict(self._latest_state)
        
        state["system"] = {
            "timestamp_robot": datetime.utcnow().isoformat() + "Z",
            "ros2_initialized": self._initialized
        }
        
        return state