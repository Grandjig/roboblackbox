"""RobotBlackBox - Real-time observability for robot fleets"""

__version__ = "0.1.0"

from robotblackbox.agent import BlackBoxAgent
from robotblackbox.config import Config

__all__ = ["BlackBoxAgent", "Config", "__version__"]
