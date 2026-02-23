# RobotBlackBox

**Real-time observability for robot fleets.**

When your robot fails at 3am, RobotBlackBox tells you exactly what happened — in seconds, not hours.

## Quick Start

### 1. Deploy the Server (once)

```bash
cd server
docker compose up -d
```

Dashboard: http://localhost:3000  
API: http://localhost:8000

### 2. Install Agent on Robot

```bash
pip install robotblackbox
```

### 3. Start Collecting

```bash
# With ROS2
rbb start --robot-id my_robot --server ws://your-server:8000

# Without ROS2 (mock data for testing)
rbb start --robot-id test_robot --mock
```

## Commands

```bash
rbb start            # Start agent
rbb config --init    # Create config file
rbb config --show    # Show current config
rbb test-connection  # Test server connection
```

## Configuration

Environment variables (prefix `RBB_`):

```bash
export RBB_ROBOT_ID=my_robot
export RBB_SERVER_URL=wss://blackbox.example.com
export RBB_COLLECTION_HZ=10
```

Or create `~/.robotblackbox/config.json`.

## ROS2 Topics

The agent subscribes to:
- `/joint_states` (sensor_msgs/JointState)
- `/robot/task_status` (std_msgs/String, JSON)
- `/model/action_confidence` (std_msgs/Float32)

Customize via config or CLI flags.

## Architecture

```
Robot                          Your Server
┌──────────────┐              ┌─────────────────┐
│ ROS2 Robot   │              │ docker compose  │
│    │         │   WebSocket  │ ┌─────────────┐ │
│ rbb agent ───┼──────────────┼─│ Backend API │ │
│              │              │ └──────┬──────┘ │
└──────────────┘              │        │        │
                              │ ┌──────▼──────┐ │
                              │ │ TimescaleDB │ │
                              │ └─────────────┘ │
                              │ ┌─────────────┐ │
                              │ │  Dashboard  │ │
                              │ └─────────────┘ │
                              └─────────────────┘
```

## Failure Detection

| Type | Trigger |
|------|--------|
| sensor | Null joint encoder values |
| motor | Torque > 50Nm or 4σ anomaly |
| model | Confidence < 45% |
| system | Low battery < 15% |

## License

MIT
