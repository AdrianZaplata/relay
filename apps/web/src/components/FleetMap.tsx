import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip } from 'react-leaflet'
import { LOW_BATTERY_PCT, MARKER_COLORS } from '../constants'
import type { FleetPosition } from '../types'

// Berlin — the simulated fleet reports positions around here.
const BERLIN: [number, number] = [52.52, 13.405]

// CircleMarker (pure SVG) instead of the default Marker on purpose: it sidesteps
// Leaflet's broken default-icon asset paths under Vite, and lets the dot encode
// state by colour — green = active & healthy, red = low battery, slate = not in service.
function markerColor(p: FleetPosition): string {
  if (p.status !== 'active') return MARKER_COLORS.off
  if (p.battery != null && p.battery < LOW_BATTERY_PCT) return MARKER_COLORS.low
  return MARKER_COLORS.active
}

export function FleetMap({ positions }: { positions: FleetPosition[] }) {
  return (
    <MapContainer className="map" center={BERLIN} zoom={13} scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {positions.map((p) => (
        <CircleMarker
          key={p.asset_id}
          center={[p.lat, p.lng]}
          radius={9}
          pathOptions={{ color: '#ffffff', weight: 2, fillColor: markerColor(p), fillOpacity: 0.9 }}
        >
          <Tooltip direction="top">{p.name}</Tooltip>
          <Popup>
            <div className="map-popup">
              <strong>{p.name}</strong>
              <div className="muted">
                {p.type} · #{p.asset_id}
              </div>
              <dl>
                <div>
                  <dt>Status</dt>
                  <dd>{p.status}</dd>
                </div>
                <div>
                  <dt>Battery</dt>
                  <dd>{p.battery != null ? `${p.battery.toFixed(0)}%` : '—'}</dd>
                </div>
                <div>
                  <dt>Speed</dt>
                  <dd>{p.speed != null ? `${p.speed.toFixed(1)} km/h` : '—'}</dd>
                </div>
              </dl>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
