import { useState, type FormEvent } from 'react'
import { api } from '../api'
import type { Asset } from '../types'
import { StatusBadge } from './StatusBadge'

interface Props {
  assets: Asset[]
  selectedId: number | null
  onSelect: (id: number) => void
  onCreated: () => void
}

export function AssetsTable({ assets, selectedId, onSelect, onCreated }: Props) {
  const [name, setName] = useState('')
  const [type, setType] = useState('ebike')
  const [busy, setBusy] = useState(false)

  async function create(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setBusy(true)
    try {
      await api.createAsset(name.trim(), type.trim() || 'asset')
      setName('')
      onCreated()
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="panel-head">
        <h2>
          Assets <span className="count">{assets.length}</span>
        </h2>
      </div>

      <form className="create-form" onSubmit={create}>
        <input placeholder="New asset name…" value={name} onChange={(e) => setName(e.target.value)} />
        <input className="type" placeholder="type" value={type} onChange={(e) => setType(e.target.value)} />
        <button disabled={busy || !name.trim()}>Add</button>
      </form>

      <table className="assets">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Status</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((a) => (
            <tr
              key={a.id}
              className={a.id === selectedId ? 'sel' : ''}
              onClick={() => onSelect(a.id)}
            >
              <td>{a.name}</td>
              <td className="muted">{a.type}</td>
              <td>
                <StatusBadge status={a.status} />
              </td>
              <td className="muted">{timeAgo(a.updated_at)}</td>
            </tr>
          ))}
          {assets.length === 0 && (
            <tr>
              <td colSpan={4} className="muted pad">
                No assets yet — add one above.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </>
  )
}

function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}
