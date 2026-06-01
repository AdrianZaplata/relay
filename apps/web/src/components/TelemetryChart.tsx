import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Telemetry } from '../types'

export function TelemetryChart({ data }: { data: Telemetry[] }) {
  const points = data.map((d) => ({
    t: new Date(d.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    value: d.value,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef0f3" />
        <XAxis dataKey="t" tick={{ fontSize: 11 }} minTickGap={48} stroke="#9aa3af" />
        <YAxis tick={{ fontSize: 11 }} stroke="#9aa3af" domain={['auto', 'auto']} width={44} />
        <Tooltip
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
          labelStyle={{ color: '#6b7280' }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="#2f6df6"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
