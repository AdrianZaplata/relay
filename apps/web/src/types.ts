export type AssetStatus = 'provisioned' | 'active' | 'maintenance' | 'retired'

export interface Asset {
  id: number
  name: string
  type: string
  status: AssetStatus
  created_at: string
  updated_at: string
}

export interface AssetEvent {
  id: number
  asset_id: number
  from_status: AssetStatus | null
  to_status: AssetStatus
  reason: string | null
  created_at: string
}

export interface Telemetry {
  id: number
  asset_id: number
  metric: string
  value: number
  recorded_at: string
}
