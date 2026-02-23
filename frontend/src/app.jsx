import { useState, useEffect, useRef } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const BACKEND_WS = 'ws://localhost:8000'
const BACKEND_API = 'http://localhost:8000'

export default function App() {
  const [connected, setConnected] = useState(false)
  const [robotId, setRobotId] = useState('robot_001')
  const [telemetry, setTelemetry] = useState([])
  const [failures, setFailures] = useState([])
  const [sessions, setSessions] = useState([])
  const [selectedSession, setSelectedSession] = useState(null)
  const [replayData, setReplayData] = useState([])
  const [replayIndex, setReplayIndex] = useState(0)
  const [isReplaying, setIsReplaying] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    connectWebSocket()
    fetchSessions()
    fetchFailures()
    return () => wsRef.current?.close()
  }, [robotId])

  const connectWebSocket = () => {
    const ws = new WebSocket(`${BACKEND_WS}/ws/dashboard`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      ws.send(JSON.stringify({ type: 'subscribe', robot_id: robotId }))
    }

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'telemetry') {
        setTelemetry(prev => {
          const next = [...prev, { ...msg, time: new Date(msg.timestamp).toLocaleTimeString() }]
          return next.slice(-100)
        })
      } else if (msg.type === 'failure') {
        setFailures(prev => [msg.failure, ...prev].slice(0, 50))
      }
    }

    ws.onclose = () => {
      setConnected(false)
      setTimeout(connectWebSocket, 3000)
    }
  }

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${BACKEND_API}/api/sessions?robot_id=${robotId}`)
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch (e) { console.error(e) }
  }

  const fetchFailures = async () => {
    try {
      const res = await fetch(`${BACKEND_API}/api/failures?robot_id=${robotId}&limit=20`)
      const data = await res.json()
      setFailures(data.failures || [])
    } catch (e) { console.error(e) }
  }

  const loadReplay = async (sessionId) => {
    setSelectedSession(sessionId)
    try {
      const res = await fetch(`${BACKEND_API}/api/sessions/${sessionId}/telemetry`)
      const data = await res.json()
      setReplayData(data.telemetry || [])
      setReplayIndex(0)
    } catch (e) { console.error(e) }
  }

  useEffect(() => {
    if (!isReplaying || replayIndex >= replayData.length) return
    const timer = setTimeout(() => setReplayIndex(i => i + 1), 100)
    return () => clearTimeout(timer)
  }, [isReplaying, replayIndex, replayData])

  const severityColor = (sev) => {
    if (sev === 'critical') return 'bg-red-600'
    if (sev === 'high') return 'bg-orange-500'
    if (sev === 'medium') return 'bg-yellow-500'
    return 'bg-blue-500'
  }

  return (
    <div className="min-h-screen p-4">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-green-400">⬛ RobotBlackBox</h1>
        <div className="flex items-center gap-4">
          <input
            type="text"
            value={robotId}
            onChange={(e) => setRobotId(e.target.value)}
            className="bg-zinc-800 px-3 py-1 rounded border border-zinc-700"
            placeholder="robot_id"
          />
          <span className={`px-2 py-1 rounded text-sm ${connected ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
            {connected ? 'LIVE' : 'DISCONNECTED'}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-3 gap-4">
        {/* Live Confidence Chart */}
        <div className="col-span-2 bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm text-zinc-400 mb-2">Model Confidence (Live)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={telemetry}>
              <XAxis dataKey="time" tick={{ fill: '#666', fontSize: 10 }} />
              <YAxis domain={[0, 1]} tick={{ fill: '#666', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }} />
              <Line type="monotone" dataKey="model_confidence" stroke="#22c55e" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Failure Alerts */}
        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800 max-h-[300px] overflow-y-auto">
          <h2 className="text-sm text-zinc-400 mb-2">Failure Alerts</h2>
          {failures.length === 0 ? (
            <p className="text-zinc-600 text-sm">No failures detected</p>
          ) : (
            <ul className="space-y-2">
              {failures.map((f, i) => (
                <li key={f.id || i} className="text-sm border-l-4 pl-2" style={{ borderColor: f.severity === 'critical' ? '#dc2626' : f.severity === 'high' ? '#f97316' : '#eab308' }}>
                  <span className={`text-xs px-1 rounded ${severityColor(f.severity)} text-white`}>{f.failure_type}</span>
                  <p className="text-zinc-300 mt-1">{f.summary}</p>
                  <p className="text-zinc-600 text-xs">{f.timestamp || new Date(f.detected_at).toLocaleString()}</p>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Session List */}
        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm text-zinc-400 mb-2">Sessions</h2>
          <ul className="space-y-1 max-h-[200px] overflow-y-auto">
            {sessions.map((s) => (
              <li key={s.id} onClick={() => loadReplay(s.id)} className={`cursor-pointer text-sm px-2 py-1 rounded hover:bg-zinc-800 ${selectedSession === s.id ? 'bg-zinc-700' : ''}`}>
                <span className="text-zinc-300">{new Date(s.started_at).toLocaleString()}</span>
                {s.failure_count > 0 && <span className="ml-2 text-red-400 text-xs">({s.failure_count} failures)</span>}
              </li>
            ))}
          </ul>
        </div>

        {/* Session Replay */}
        <div className="col-span-2 bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm text-zinc-400">Session Replay</h2>
            {replayData.length > 0 && (
              <div className="flex items-center gap-2">
                <button onClick={() => setIsReplaying(!isReplaying)} className="px-3 py-1 bg-zinc-700 rounded text-sm hover:bg-zinc-600">
                  {isReplaying ? 'Pause' : 'Play'}
                </button>
                <input
                  type="range"
                  min={0}
                  max={replayData.length - 1}
                  value={replayIndex}
                  onChange={(e) => { setReplayIndex(+e.target.value); setIsReplaying(false) }}
                  className="w-48"
                />
                <span className="text-xs text-zinc-500">{replayIndex + 1}/{replayData.length}</span>
              </div>
            )}
          </div>
          {replayData.length > 0 ? (
            <div className="grid grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-zinc-500">Time</p>
                <p className="text-zinc-200">{new Date(replayData[replayIndex]?.time).toLocaleTimeString()}</p>
              </div>
              <div>
                <p className="text-zinc-500">Confidence</p>
                <p className={replayData[replayIndex]?.model_confidence < 0.5 ? 'text-red-400' : 'text-green-400'}>
                  {(replayData[replayIndex]?.model_confidence * 100)?.toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-zinc-500">Task Phase</p>
                <p className="text-zinc-200">{replayData[replayIndex]?.task_phase || '-'}</p>
              </div>
              <div>
                <p className="text-zinc-500">Battery</p>
                <p className="text-zinc-200">{replayData[replayIndex]?.battery_percent?.toFixed(0)}%</p>
              </div>
            </div>
          ) : (
            <p className="text-zinc-600 text-sm">Select a session to replay</p>
          )}
        </div>
      </div>
    </div>
  )
}