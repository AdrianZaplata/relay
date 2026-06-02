// Poll cadence shared by the live console (AssetDetail) and the map (MapView).
export const POLL_MS = 3000

// Battery percentage below which a bike is flagged low (its marker turns red).
export const LOW_BATTERY_PCT = 25

// Fleet-map marker colours. Kept in sync with the legend dots in index.css
// (--active / --retired / --provisioned), so markerColor and the legend can't drift.
export const MARKER_COLORS = {
  active: '#16a34a',
  low: '#dc2626',
  off: '#64748b',
} as const
