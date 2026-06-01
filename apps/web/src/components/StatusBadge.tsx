import type { AssetStatus } from '../types'

export function StatusBadge({ status }: { status: AssetStatus }) {
  return <span className={`badge ${status}`}>{status}</span>
}
