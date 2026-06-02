import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { AssetDetail } from './components/AssetDetail'
import { AssetsTable } from './components/AssetsTable'
import { MapView } from './components/MapView'
import type { Asset } from './types'

export default function App() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'console' | 'map'>('console')

  const refresh = useCallback(async () => {
    try {
      const data = await api.listAssets()
      setAssets(data)
      setConnected(true)
      setError(null)
      setSelectedId((prev) => prev ?? data[0]?.id ?? null)
    } catch (e) {
      setConnected(false)
      setError(e instanceof Error ? e.message : 'failed to reach API')
    }
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 3000)
    return () => clearInterval(timer)
  }, [refresh])

  const selected = assets.find((a) => a.id === selectedId) ?? null

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◇</span>
          <span className="name">Relay</span>
          <span className="subtitle">Operator Console</span>
        </div>
        <div className="views">
          <button className={view === 'console' ? 'on' : ''} onClick={() => setView('console')}>
            Console
          </button>
          <button className={view === 'map' ? 'on' : ''} onClick={() => setView('map')}>
            Map
          </button>
        </div>
        <div className={`conn ${connected ? 'ok' : 'down'}`}>
          <span className="dot" />
          {connected ? 'live' : 'reconnecting…'}
        </div>
      </header>

      {view === 'console' ? (
        <main className="layout">
          <section className="panel assets-panel">
            <AssetsTable
              assets={assets}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onCreated={refresh}
            />
          </section>
          <section className="panel detail-panel">
            {selected ? (
              <AssetDetail asset={selected} onChanged={refresh} />
            ) : (
              <div className="empty">Select an asset to view telemetry and lifecycle.</div>
            )}
          </section>
        </main>
      ) : (
        <MapView />
      )}

      {error && <div className="error-toast">API unreachable: {error}</div>}
    </div>
  )
}
