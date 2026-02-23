# ⬛ RobotBlackBox

**Know exactly why your robot failed.**

Open-source black box recorder for ROS2 robots. Real-time failure detection, session replay, and fleet observability.

[![Deploy to GitHub Pages](https://github.com/Grandjig/roboblackbox/actions/workflows/deploy.yml/badge.svg)](https://github.com/Grandjig/roboblackbox/actions/workflows/deploy.yml)

## 🚀 Quick Links

- **[Live Demo Dashboard](https://grandjig.github.io/roboblackbox/dashboard/)** - Try it now with mock data
- **[Landing Page](https://grandjig.github.io/roboblackbox/)** - Product overview
- **[Documentation](#documentation)** - Setup guide

## ✨ Features

- 🔴 **Real-time Failure Detection** - Sensor dropouts, motor overloads, AI uncertainty
- ⏪ **Session Replay** - Scrub through past sessions like a DVR
- 📊 **Fleet Dashboard** - All robots on one screen
- 🤖 **ROS2 Native** - One command install, automatic topic subscription
- 💬 **Plain English** - "Joint 3 encoder null" not error code 0x4F2A
- 🔒 **Privacy First** - Self-host or use cloud, your choice

## 📦 Installation

### On your robot:

```bash
pip install robotblackbox
rbb start --robot-id my_robot --server wss://your-backend.com
```

### Test without ROS2:

```bash
pip install robotblackbox
rbb start --robot-id test_robot --mock
```

## 🏗️ Architecture

```
┌─────────────────┐         ┌─────────────────────────────┐
│   Your Robot    │         │      Your Infrastructure    │
│                 │         │                             │
│  ┌───────────┐  │  WSS    │  ┌─────────┐  ┌──────────┐ │
│  │ ROS2      │  ├────────►│  │ Backend │  │ Dashboard│ │
│  │           │  │         │  │ (API)   │  │ (React)  │ │
│  │ rbb agent │  │         │  └────┬────┘  └──────────┘ │
│  └───────────┘  │         │       │                    │
└─────────────────┘         │  ┌────▼────┐               │
                            │  │ Database│               │
                            │  │(optional)│              │
                            │  └─────────┘               │
                            └─────────────────────────────┘
```

## 🌐 Hosting Options

### Frontend (Dashboard)

**GitHub Pages** (Free) - Already configured!
```bash
git push origin main  # Auto-deploys to grandjig.github.io/roboblackbox
```

### Backend (API)

**Option 1: Railway** (Free tier: 500 hours/month)
1. Connect repo: https://railway.app/new
2. Deploy from GitHub
3. Set `PORT` env var
4. Get your URL: `https://your-app.up.railway.app`

**Option 2: Render** (Free tier: 750 hours/month)
1. Connect repo: https://render.com/new
2. Select "Web Service"
3. It auto-detects `render.yaml`

**Option 3: Fly.io** (Free tier: 3 shared VMs)
```bash
fly launch
fly deploy
```

### Connecting Dashboard to Backend

In browser console:
```javascript
localStorage.setItem('RBB_API_URL', 'https://your-backend.railway.app');
localStorage.setItem('RBB_WS_URL', 'wss://your-backend.railway.app');
location.reload();
```

## 🧪 Development

### Run everything locally:

```powershell
# Windows
.\start.ps1
```

```bash
# Linux/Mac
# Terminal 1: Backend
cd backend && pip install -r requirements.txt && python main.py

# Terminal 2: Frontend
cd frontend && npm install && npm run dev

# Terminal 3: Mock Agent
cd agent && pip install websockets psutil && python agent.py --mock
```

Then open: http://localhost:3000

## 📁 Project Structure

```
roboblackbox/
├── docs/                    # GitHub Pages (landing + dashboard)
│   ├── index.html          # Landing page
│   └── dashboard/          # React dashboard (pre-built)
├── backend/                 # FastAPI server (deploy to Railway/Render)
│   ├── main.py
│   ├── classifier/
│   └── db/
├── agent/                   # Runs on robot
│   ├── agent.py
│   └── collectors/
├── frontend/                # Development version (Vite + React)
├── robotblackbox/           # pip installable package
├── .github/workflows/       # Auto-deploy to GitHub Pages
├── railway.json             # Railway config
├── render.yaml              # Render config
└── start.ps1                # Windows local dev script
```

## 💰 Business Model

**Free Tier** (This repo, self-hosted):
- Unlimited robots
- Rule-based classifier
- Session replay
- 30-day history

**Team** ($99/robot/month):
- ML-powered classifier (trained on community data)
- Fleet management
- 1-year history
- Slack/PagerDuty alerts

**Enterprise** (Custom):
- Predictive failure
- Compliance audit logs
- On-premise
- SLA

## 🤝 Contributing

PRs welcome! The agent is Apache 2.0 licensed. The ML classifier (coming soon) will be proprietary.

## 📜 License

Apache 2.0 - See [LICENSE](LICENSE)

---

**Built for robots that need to explain themselves.**