import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from '../api'
import { POLL_MS } from '../constants'
import type { Asset, AssetEvent, AssetStatus, Telemetry } from '../types'
import { StatusBadge } from './StatusBadge'
import { TelemetryChart } from './TelemetryChart'

// Client-side mirror of the server state machine — drives which buttons show.
// The server is the source of truth and rejects anything illegal with 409.
const NEXT: Record<AssetStatus, AssetStatus[]> = {
  provisioned: ['active'],
  active: ['maintenance', 'retired'],
  maintenance: ['active', 'retired'],
  retired: [],
}

export function AssetDetail({ asset, onChanged }: { asset: Asset; onChanged: () => void }) {
  const [telemetry, setTelemetry] = useState<Telemetry[]>([])
  const [events, setEvents] = useState<AssetEvent[]>([])
  const [msg, setMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [t, e] = await Promise.all([api.telemetry(asset.id), api.events(asset.id)])
      setTelemetry(t)
      setEvents(e)
    } catch {
      /* transient poll error — keep last good data */
    }
  }, [asset.id])

  useEffect(() => {
    setMsg(null)
    load()
    const timer = setInterval(load, POLL_MS)
    return () => clearInterval(timer)
  }, [load])

  async function go(to: AssetStatus) {
    setMsg(null)
    try {
      await api.transition(asset.id, to)
      onChanged()
    } catch (e) {
      setMsg(e instanceof ApiError ? `Rejected (${e.status}): ${e.message}` : 'Request failed')
    }
  }

  const latest = telemetry.length ? telemetry[telemetry.length - 1] : null

  return (
    <div className="detail">
      <div className="detail-head">
        <div>
          <h2>{asset.name}</h2>
          <div className="muted">
            {asset.type} · #{asset.id}
          </div>
        </div>
        <StatusBadge status={asset.status} />
      </div>

      <div className="actions">
        <span className="actions-label">Lifecycle</span>
        {NEXT[asset.status].length === 0 ? (
          <span className="muted">terminal state — no transitions</span>
        ) : (
          NEXT[asset.status].map((to) => (
            <button key={to} className={`btn ${to}`} onClick={() => go(to)}>
              → {to}
            </button>
          ))
        )}
      </div>
      {msg && <div className="reject">{msg}</div>}

      <div className="card">
        <div className="card-head">
          <h3>Telemetry · battery</h3>
          {latest && <span className="latest">{latest.value.toFixed(1)}</span>}
        </div>
        {telemetry.length > 0 ? (
          <TelemetryChart data={telemetry} />
        ) : (
          <div className="muted chart-empty">
            No telemetry yet. Active assets stream readings through Kafka.
          </div>
        )}
      </div>

      <div className="card">
        <h3>Lifecycle history</h3>
        <ul className="timeline">
          {events
            .slice()
            .reverse()
            .map((ev) => (
              <li key={ev.id}>
                <span className="muted">{new Date(ev.created_at).toLocaleTimeString()}</span>{' '}
                {ev.from_status ?? '∅'} → <strong>{ev.to_status}</strong>
                {ev.reason && <span className="muted"> · {ev.reason}</span>}
              </li>
            ))}
          {events.length === 0 && <li className="muted">No transitions yet.</li>}
        </ul>
      </div>
    </div>
  )
}
