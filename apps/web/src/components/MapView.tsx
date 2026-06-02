import { useEffect, useState } from 'react'
import { api } from '../api'
import { POLL_MS } from '../constants'
import type { FleetPosition } from '../types'
import { FleetMap } from './FleetMap'

// Consecutive poll failures before we warn the operator the map may be stale —
// a frozen map of last-known positions must not read as live during an outage.
const STALE_AFTER_FAILURES = 3

// Owns polling of the fleet's latest GPS fixes (same cadence as AssetDetail) and
// renders the map plus a legend with the live reporting-bike count.
export function MapView() {
  const [positions, setPositions] = useState<FleetPosition[]>([])
  const [stale, setStale] = useState(false)

  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>
    let failures = 0

    const tick = async () => {
      try {
        const next = await api.fleetPositions()
        if (!active) return
        setPositions(next)
        failures = 0
        setStale(false)
      } catch {
        // Transient poll error — keep the last good positions on screen, but
        // surface a warning once several land in a row.
        if (!active) return
        failures += 1
        if (failures >= STALE_AFTER_FAILURES) setStale(true)
      } finally {
        // Reschedule only after this poll settles, so a slow response can't
        // overlap the next request or land out of order and clobber fresh data.
        if (active) timer = setTimeout(tick, POLL_MS)
      }
    }

    tick()
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [])

  return (
    <div className="map-view">
      <FleetMap positions={positions} />
      <div className="map-legend">
        <span className="legend-title">
          {positions.length} {positions.length === 1 ? 'bike' : 'bikes'} reporting
        </span>
        <span className="legend-item">
          <span className="legend-dot ok" /> active
        </span>
        <span className="legend-item">
          <span className="legend-dot low" /> low battery
        </span>
        <span className="legend-item">
          <span className="legend-dot off" /> not in service
        </span>
      </div>
      {stale && <div className="map-stale">Connection lost — positions may be stale</div>}
    </div>
  )
}
