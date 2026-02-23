"""ROS2 Collector - collects data from real ROS2 robot"""

import asyncio
import threading
from datetime import datetime
from typing import Optional


class ROS2Collector:
    """
    Collects telemetry from a ROS2 robot.
    
    Subscribes to:
    - /joint_states (sensor_msgs/JointState)
    - /robot/task_status (std_msgs/String, JSON)
    - /model/action_confidence (std_msgs/Float32)
    
    Customize topics via constructor args or config.
    """
    
    def __init__(
        self,
        robot_id: str,
        joint_states_topic: str = "/joint_states",
        task_status_topic: str = "/robot/task_status",
        model_confidence_topic: str = "/model/action_confidence",
    ):
        self.robot_id = robot_id
        self.joint_states_topic = joint_states_topic
        self.task_status_topic = task_status_topic
        self.model_confidence_topic = model_confidence_topic
        
        self._latest_state = {}
        self._lock = threading.Lock()
        self._initialized = False
        
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
                    super().__init__("robotblackbox_agent")
                    
                    inner_self.create_subscription(
                        JointState,
                        self.joint_states_topic,
                        lambda msg: self._on_joint_states(msg),
                        10
                    )
                    inner_self.create_subscription(
                        String,
                        self.task_status_topic,
                        lambda msg: self._on_task_status(msg),
                        10
                    )
                    inner_self.create_subscription(
                        Float32,
                        self.model_confidence_topic,
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
                "temperatures_c": [],
            }
    
    def _on_task_status(self, msg):
        with self._lock:
            try:
                import json
                self._latest_state["task"] = json.loads(msg.data)
            except Exception:
                self._latest_state["task"] = {"raw": msg.data}
    
    def _on_model_confidence(self, msg):
        with self._lock:
            if "model" not in self._latest_state:
                self._latest_state["model"] = {}
            self._latest_state["model"]["action_confidence"] = msg.data
            self._latest_state["model"]["uncertainty"] = 1.0 - msg.data
    
    async def get_state(self) -> dict:
        await asyncio.sleep(0)
        with self._lock:
            state = dict(self._latest_state)
        
        state["system"] = {
            "timestamp_robot": datetime.utcnow().isoformat() + "Z",
            "ros2_initialized": self._initialized,
        }
        return state
