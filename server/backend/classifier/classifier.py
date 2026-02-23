"""Failure Classifier - detects robot failures from telemetry"""

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
        self.values: deque = deque(maxlen=window)
    
    def update(self, value: float):
        if value is not None:
            self.values.append(value)
    
    @property
    def mean(self) -> Optional[float]:
        return sum(self.values) / len(self.values) if self.values else None
    
    @property
    def std(self) -> Optional[float]:
        if len(self.values) < 2:
            return None
        m = self.mean
        return (sum((x - m) ** 2 for x in self.values) / len(self.values)) ** 0.5
    
    def is_anomaly(self, value: float, sigma: float = 3.0) -> bool:
        if self.std is None or self.std == 0:
            return False
        return abs(value - self.mean) > (sigma * self.std)


class FailureClassifier:
    TORQUE_OVERLOAD_NM = 50.0
    CONFIDENCE_LOW = 0.45
    CONFIDENCE_CRITICAL = 0.25
    TEMP_WARNING_C = 60.0
    BATTERY_LOW = 15.0
    
    def __init__(self):
        self._confidence_stats: Dict[str, RollingStats] = {}
        self._torque_stats: Dict[str, List[RollingStats]] = {}
        self._consecutive: Dict[str, int] = {}
    
    def classify(self, robot_id: str, data: dict) -> FailureResult:
        joints = data.get("joints", {})
        model = data.get("model", {})
        system = data.get("system", {})
        
        # Update stats
        confidence = model.get("action_confidence")
        if confidence is not None:
            if robot_id not in self._confidence_stats:
                self._confidence_stats[robot_id] = RollingStats(100)
            self._confidence_stats[robot_id].update(confidence)
        
        # Rule 1: Sensor dropout
        positions = joints.get("positions_rad", [])
        null_joints = [i for i, p in enumerate(positions) if p is None]
        if null_joints:
            return self._result(robot_id, True, "sensor", "high", 0.95,
                f"Sensor dropout on joint(s) {null_joints}",
                f"Joint encoder(s) {null_joints} returned null. Check connections.",
                {"joints": null_joints}, {"null_joints": null_joints})
        
        # Rule 2: Motor overload
        torques = joints.get("torques_nm", [])
        overloaded = [i for i, t in enumerate(torques) if t and t > self.TORQUE_OVERLOAD_NM]
        if overloaded:
            return self._result(robot_id, True, "motor", "high", 0.90,
                f"Motor overload on joint(s) {overloaded}",
                "Abnormal torque detected. Check for obstructions.",
                {"joints": overloaded}, {"torques": torques})
        
        # Rule 3: Model uncertainty
        if confidence is not None:
            if confidence < self.CONFIDENCE_CRITICAL:
                return self._result(robot_id, True, "model", "critical", 0.88,
                    f"AI model critically uncertain ({confidence:.0%})",
                    "Model in unfamiliar situation. Consider stopping robot.",
                    {"confidence": confidence}, {})
            if confidence < self.CONFIDENCE_LOW:
                return self._result(robot_id, True, "model", "medium", 0.80,
                    f"AI model low confidence ({confidence:.0%})",
                    "Model uncertain. Monitor closely.",
                    {"confidence": confidence}, {})
        
        # Rule 4: Low battery
        battery = system.get("battery_percent")
        if battery is not None and battery < self.BATTERY_LOW:
            return self._result(robot_id, True, "system", "medium", 1.0,
                f"Low battery ({battery:.0f}%)", "Return to charging station.",
                {"battery": battery}, {})
        
        self._consecutive[robot_id] = 0
        return FailureResult(False, "none", "none", 1.0, "OK", "", {}, {})
    
    def _result(self, robot_id, is_failure, ftype, severity, conf, summary, detail, affected, data):
        self._consecutive[robot_id] = self._consecutive.get(robot_id, 0) + 1
        return FailureResult(is_failure, ftype, severity, conf, summary, detail, affected, data)


classifier = FailureClassifier()
