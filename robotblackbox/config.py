"""Configuration management for RobotBlackBox agent"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Config(BaseSettings):
    """Agent configuration - can be set via env vars or config file"""
    
    # Required
    robot_id: str = Field(default="robot_001", description="Unique robot identifier")
    
    # Server connection
    server_url: str = Field(
        default="ws://localhost:8000",
        description="WebSocket URL of RobotBlackBox server"
    )
    
    # Collection settings
    collection_hz: float = Field(default=10.0, description="Telemetry collection rate")
    buffer_max: int = Field(default=1000, description="Max events to buffer if disconnected")
    
    # Collector type
    use_mock: bool = Field(default=False, description="Use mock data instead of ROS2")
    
    # ROS2 topics (customize for your robot)
    ros2_joint_states_topic: str = Field(default="/joint_states")
    ros2_task_status_topic: str = Field(default="/robot/task_status")
    ros2_model_confidence_topic: str = Field(default="/model/action_confidence")
    
    # Data sharing (opt-in for community classifier improvement)
    share_anonymized_failures: bool = Field(
        default=True,
        description="Share anonymized failure events to improve classifier for everyone"
    )
    
    # Local storage
    local_cache_dir: Path = Field(
        default=Path.home() / ".robotblackbox",
        description="Local cache directory for offline data"
    )
    
    class Config:
        env_prefix = "RBB_"
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @classmethod
    def from_file(cls, path: Path) -> "Config":
        """Load config from TOML/JSON file"""
        import json
        if path.suffix == ".json":
            with open(path) as f:
                return cls(**json.load(f))
        raise ValueError(f"Unsupported config format: {path.suffix}")
    
    def save(self, path: Optional[Path] = None):
        """Save current config"""
        import json
        path = path or (self.local_cache_dir / "config.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=2, default=str)
