import type { Asset, AssetEvent, FleetPosition, Telemetry } from './types'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

const json = { 'content-type': 'application/json' }

export const api = {
  listAssets: () => fetch(`${BASE}/assets`).then((r) => handle<Asset[]>(r)),

  createAsset: (name: string, type: string) =>
    fetch(`${BASE}/assets`, {
      method: 'POST',
      headers: json,
      body: JSON.stringify({ name, type }),
    }).then((r) => handle<Asset>(r)),

  transition: (id: number, to_status: string, reason?: string) =>
    fetch(`${BASE}/assets/${id}/transition`, {
      method: 'POST',
      headers: json,
      body: JSON.stringify({ to_status, reason }),
    }).then((r) => handle<Asset>(r)),

  telemetry: (id: number, metric = 'battery') =>
    fetch(`${BASE}/assets/${id}/telemetry?metric=${metric}&limit=200`).then((r) =>
      handle<Telemetry[]>(r),
    ),

  events: (id: number) => fetch(`${BASE}/assets/${id}/events`).then((r) => handle<AssetEvent[]>(r)),

  fleetPositions: () => fetch(`${BASE}/fleet/positions`).then((r) => handle<FleetPosition[]>(r)),
}
