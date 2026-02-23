-- RobotBlackBox TimescaleDB Schema
-- Auto-runs on container init via docker-entrypoint-initdb.d

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    robot_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sessions_robot_id ON sessions(robot_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at DESC);

-- Telemetry table (hypertable for time-series)
CREATE TABLE IF NOT EXISTS telemetry (
    time TIMESTAMPTZ NOT NULL,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    robot_id TEXT NOT NULL,
    
    -- Joints
    joint_positions DOUBLE PRECISION[],
    joint_velocities DOUBLE PRECISION[],
    joint_torques DOUBLE PRECISION[],
    joint_temps DOUBLE PRECISION[],
    
    -- Gripper
    gripper_position DOUBLE PRECISION,
    gripper_force DOUBLE PRECISION,
    gripper_contact BOOLEAN,
    
    -- Task
    task_name TEXT,
    task_phase TEXT,
    task_progress DOUBLE PRECISION,
    
    -- Model
    model_confidence DOUBLE PRECISION,
    model_uncertainty DOUBLE PRECISION,
    model_inference_ms DOUBLE PRECISION,
    model_action TEXT,
    
    -- System
    cpu_percent DOUBLE PRECISION,
    memory_mb DOUBLE PRECISION,
    battery_percent DOUBLE PRECISION,
    network_latency_ms DOUBLE PRECISION,
    
    -- Raw JSON for anything else
    raw_data JSONB
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_telemetry_session ON telemetry(session_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_robot ON telemetry(robot_id, time DESC);

-- Failures table
CREATE TABLE IF NOT EXISTS failures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    robot_id TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    failure_type TEXT NOT NULL,  -- sensor, motor, model, network, system
    severity TEXT NOT NULL,       -- low, medium, high, critical
    confidence DOUBLE PRECISION,
    
    summary TEXT NOT NULL,
    detail TEXT,
    
    context_start TIMESTAMPTZ,
    context_end TIMESTAMPTZ,
    
    affected_components JSONB DEFAULT '{}',
    classifier_data JSONB DEFAULT '{}',
    
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_failures_session ON failures(session_id);
CREATE INDEX IF NOT EXISTS idx_failures_robot ON failures(robot_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_failures_type ON failures(failure_type);
CREATE INDEX IF NOT EXISTS idx_failures_severity ON failures(severity);

-- Events table (general logging)
CREATE TABLE IF NOT EXISTS events (
    time TIMESTAMPTZ NOT NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    robot_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT,
    message TEXT,
    data JSONB DEFAULT '{}'
);

SELECT create_hypertable('events', 'time', if_not_exists => TRUE);