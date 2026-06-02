import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { FleetPosition } from '../types'
import { FleetMap } from './FleetMap'

// Owns polling of the fleet's latest GPS fixes (same 3s cadence as AssetDetail)
// and renders the map plus a legend with the live reporting-bike count.
export function MapView() {
  const [positions, setPositions] = useState<FleetPosition[]>([])

  const load = useCallback(async () => {
    try {
      setPositions(await api.fleetPositions())
    } catch {
      /* transient poll error — keep the last good positions on screen */
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 3000)
    return () => clearInterval(timer)
  }, [load])

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
    </div>
  )
}
