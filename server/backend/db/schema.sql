-- RobotBlackBox TimescaleDB Schema

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    robot_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_sessions_robot ON sessions(robot_id);
CREATE INDEX idx_sessions_time ON sessions(started_at DESC);

CREATE TABLE IF NOT EXISTS telemetry (
    time TIMESTAMPTZ NOT NULL,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    robot_id TEXT NOT NULL,
    joint_positions DOUBLE PRECISION[],
    joint_velocities DOUBLE PRECISION[],
    joint_torques DOUBLE PRECISION[],
    joint_temps DOUBLE PRECISION[],
    gripper_position DOUBLE PRECISION,
    gripper_force DOUBLE PRECISION,
    gripper_contact BOOLEAN,
    task_name TEXT,
    task_phase TEXT,
    task_progress DOUBLE PRECISION,
    model_confidence DOUBLE PRECISION,
    model_uncertainty DOUBLE PRECISION,
    model_inference_ms DOUBLE PRECISION,
    model_action TEXT,
    cpu_percent DOUBLE PRECISION,
    memory_mb DOUBLE PRECISION,
    battery_percent DOUBLE PRECISION,
    raw_data JSONB
);

SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);

CREATE INDEX idx_telemetry_session ON telemetry(session_id, time DESC);
CREATE INDEX idx_telemetry_robot ON telemetry(robot_id, time DESC);

CREATE TABLE IF NOT EXISTS failures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    robot_id TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    failure_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    summary TEXT NOT NULL,
    detail TEXT,
    affected_components JSONB DEFAULT '{}',
    classifier_data JSONB DEFAULT '{}',
    acknowledged BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_failures_robot ON failures(robot_id, detected_at DESC);
CREATE INDEX idx_failures_type ON failures(failure_type);
