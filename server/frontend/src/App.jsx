import { useState, useEffect, useRef } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS = API.replace('http', 'ws')

export default function App() {
  const [connected, setConnected] = useState(false)
  const [robotId, setRobotId] = useState('robot_001')
  const [telemetry, setTelemetry] = useState([])
  const [failures, setFailures] = useState([])
  const [sessions, setSessions] = useState([])
  const [replay, setReplay] = useState({ data: [], index: 0, playing: false })
  const ws = useRef(null)

  useEffect(() => {
    connect()
    fetchSessions()
    fetchFailures()
    return () => ws.current?.close()
  }, [robotId])

  const connect = () => {
    ws.current = new WebSocket(`${WS}/ws/dashboard`)
    ws.current.onopen = () => {
      setConnected(true)
      ws.current.send(JSON.stringify({ type: 'subscribe', robot_id: robotId }))
    }
    ws.current.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'telemetry') {
        setTelemetry(prev => [...prev, { ...msg, time: new Date(msg.timestamp).toLocaleTimeString() }].slice(-100))
      } else if (msg.type === 'failure') {
        setFailures(prev => [msg.failure, ...prev].slice(0, 50))
      }
    }
    ws.current.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
  }

  const fetchSessions = async () => {
    const res = await fetch(`${API}/api/sessions?robot_id=${robotId}`)
    const data = await res.json()
    setSessions(data.sessions || [])
  }

  const fetchFailures = async () => {
    const res = await fetch(`${API}/api/failures?robot_id=${robotId}&limit=20`)
    const data = await res.json()
    setFailures(data.failures || [])
  }

  const loadReplay = async (id) => {
    const res = await fetch(`${API}/api/sessions/${id}/telemetry`)
    const data = await res.json()
    setReplay({ data: data.telemetry || [], index: 0, playing: false })
  }

  useEffect(() => {
    if (!replay.playing || replay.index >= replay.data.length) return
    const t = setTimeout(() => setReplay(r => ({ ...r, index: r.index + 1 })), 100)
    return () => clearTimeout(t)
  }, [replay])

  return (
    <div className="min-h-screen p-4">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-green-400">⬛ RobotBlackBox</h1>
        <div className="flex items-center gap-4">
          <input value={robotId} onChange={e => setRobotId(e.target.value)} className="bg-zinc-800 px-3 py-1 rounded border border-zinc-700" />
          <span className={`px-2 py-1 rounded text-sm ${connected ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
            {connected ? 'LIVE' : 'DISCONNECTED'}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm text-zinc-400 mb-2">Model Confidence</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={telemetry}>
              <XAxis dataKey="time" tick={{ fill: '#666', fontSize: 10 }} />
              <YAxis domain={[0, 1]} tick={{ fill: '#666', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }} />
              <Line type="monotone" dataKey="model_confidence" stroke="#22c55e" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800 max-h-[300px] overflow-y-auto">
          <h2 className="text-sm text-zinc-400 mb-2">Failures</h2>
          {failures.length === 0 ? <p className="text-zinc-600 text-sm">No failures</p> : (
            <ul className="space-y-2">
              {failures.map((f, i) => (
                <li key={f.id || i} className="text-sm border-l-4 pl-2" style={{ borderColor: f.severity === 'critical' ? '#dc2626' : '#f97316' }}>
                  <span className="text-xs px-1 rounded bg-red-600 text-white">{f.failure_type}</span>
                  <p className="text-zinc-300">{f.summary}</p>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <h2 className="text-sm text-zinc-400 mb-2">Sessions</h2>
          <ul className="space-y-1 max-h-[200px] overflow-y-auto">
            {sessions.map(s => (
              <li key={s.id} onClick={() => loadReplay(s.id)} className="cursor-pointer text-sm px-2 py-1 rounded hover:bg-zinc-800">
                {new Date(s.started_at).toLocaleString()}
                {s.failure_count > 0 && <span className="ml-2 text-red-400">({s.failure_count})</span>}
              </li>
            ))}
          </ul>
        </div>

        <div className="col-span-2 bg-zinc-900 rounded-lg p-4 border border-zinc-800">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm text-zinc-400">Replay</h2>
            {replay.data.length > 0 && (
              <div className="flex items-center gap-2">
                <button onClick={() => setReplay(r => ({ ...r, playing: !r.playing }))} className="px-3 py-1 bg-zinc-700 rounded text-sm">
                  {replay.playing ? 'Pause' : 'Play'}
                </button>
                <input type="range" min={0} max={replay.data.length - 1} value={replay.index} onChange={e => setReplay(r => ({ ...r, index: +e.target.value, playing: false }))} className="w-48" />
              </div>
            )}
          </div>
          {replay.data.length > 0 ? (
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div><p className="text-zinc-500">Time</p><p>{new Date(replay.data[replay.index]?.time).toLocaleTimeString()}</p></div>
              <div><p className="text-zinc-500">Confidence</p><p className={replay.data[replay.index]?.model_confidence < 0.5 ? 'text-red-400' : 'text-green-400'}>{(replay.data[replay.index]?.model_confidence * 100)?.toFixed(1)}%</p></div>
              <div><p className="text-zinc-500">Phase</p><p>{replay.data[replay.index]?.task_phase || '-'}</p></div>
            </div>
          ) : <p className="text-zinc-600 text-sm">Select a session</p>}
        </div>
      </div>
    </div>
  )
}
