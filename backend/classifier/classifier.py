import logging
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

@dataclass
class FailureResult:
    is_failure: bool
    failure_type: str
    severity: str
    confidence: float
    summary: str
    detail: str
    affected_components: Dict
    classifier_data: Dict

class RollingStats:
    def __init__(self, window: int = 50):
        self.values = deque(maxlen=window)
    
    def update(self, value):
        if value is not None:
            self.values.append(value)
    
    @property
    def mean(self):
        return sum(self.values) / len(self.values) if self.values else None
    
    @property
    def std(self):
        if len(self.values) < 2:
            return None
        m = self.mean
        return (sum((x - m) ** 2 for x in self.values) / len(self.values)) ** 0.5

class FailureClassifier:
    def __init__(self):
        self._stats = {}
    
    def classify(self, robot_id: str, data: dict) -> FailureResult:
        joints = data.get("joints", {})
        model = data.get("model", {})
        system = data.get("system", {})
        
        # Check sensor dropout
        positions = joints.get("positions_rad", [])
        null_joints = [i for i, p in enumerate(positions) if p is None]
        if null_joints:
            return FailureResult(True, "sensor", "high", 0.95,
                f"Sensor dropout on joints {null_joints}",
                "Encoder returned null. Check connections.",
                {"joints": null_joints}, {})
        
        # Check motor overload
        torques = joints.get("torques_nm", [])
        overload = [i for i, t in enumerate(torques) if t and t > 50]
        if overload:
            return FailureResult(True, "motor", "high", 0.90,
                f"Motor overload on joints {overload}",
                "High torque detected. Check for obstruction.",
                {"joints": overload}, {})
        
        # Check model confidence
        conf = model.get("action_confidence")
        if conf is not None:
            if conf < 0.25:
                return FailureResult(True, "model", "critical", 0.88,
                    f"AI critically uncertain ({conf:.0%})",
                    "Model in unfamiliar situation.",
                    {"confidence": conf}, {})
            if conf < 0.45:
                return FailureResult(True, "model", "medium", 0.80,
                    f"AI low confidence ({conf:.0%})",
                    "Model uncertain. Monitor closely.",
                    {"confidence": conf}, {})
        
        # Check battery
        battery = system.get("battery_percent")
        if battery is not None and battery < 15:
            return FailureResult(True, "system", "medium", 1.0,
                f"Low battery ({battery:.0f}%)",
                "Return to charging station.",
                {"battery": battery}, {})
        
        return FailureResult(False, "none", "none", 1.0, "OK", "", {}, {})

classifier = FailureClassifier()
