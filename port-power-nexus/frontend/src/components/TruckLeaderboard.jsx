import useRealtimeTable, { REFETCH_ON_EVENTS_INSERT } from '../hooks/useRealtimeTable'
import useSmoothSoc from '../hooks/useSmoothSoc'
import { effectiveMapStatus } from '../lib/mapTruckStatus'
import { formatSocPercent, normalizeSoc } from '../lib/truckDisplay'

function TruckCard({ truck, baysRows }) {
  const status = effectiveMapStatus(truck, baysRows)
  const socSmooth = useSmoothSoc(truck.state_of_charge ?? 0)

  let borderColor = '#1a3a5c'
  if (status === 'bidding') borderColor = '#00aaff44'
  else if (status === 'charging') borderColor = '#ffaa0044'
  else if (status === 'at_port') borderColor = '#88aacc44'

  let badgeBg = '#00ff8822'
  let badgeColor = '#00ff88'
  let label = 'IDLE'
  if (status === 'bidding') { badgeBg = '#00aaff22'; badgeColor = '#00aaff'; label = 'BIDDING' }
  else if (status === 'charging') { badgeBg = '#ffaa0022'; badgeColor = '#ffaa00'; label = 'CHARGING' }
  else if (status === 'at_port') { badgeBg = '#4a6a8a22'; badgeColor = '#88aacc'; label = 'EXIT' }
  else if (status === 'done') { badgeBg = '#3a5a6a22'; badgeColor = '#3a5a6a'; label = 'DONE' }

  const soc = normalizeSoc(socSmooth)
  let barColor = '#00ff88'
  if (soc < 30) barColor = '#cc3333'
  else if (soc <= 60) barColor = '#cc8800'

  return (
    <div style={{ background: '#0a0e1a', border: `1px solid ${borderColor}`, borderRadius: 4, padding: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: '#c8d4e8', fontSize: 13, letterSpacing: 1, fontFamily: 'Courier New, monospace', fontWeight: 'bold' }}>
          {truck.name}
        </span>
        <span style={{ fontSize: 11, padding: '2px 6px', borderRadius: 2, letterSpacing: 1, fontFamily: 'Courier New, monospace', background: badgeBg, color: badgeColor }}>
          {label}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, height: 6, background: '#1a2a3a', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${soc}%`, height: 6, background: barColor, borderRadius: 2 }} />
        </div>
        <span style={{ fontSize: 12, color: '#6a8aaa', fontFamily: 'Courier New, monospace' }}>
          {formatSocPercent(socSmooth)}
        </span>
      </div>
      {truck.destination && (
        <div style={{ marginTop: 6, fontSize: 12, color: '#aabbcc', fontFamily: 'Courier New, monospace' }}>
          DEST: {truck.destination}
        </div>
      )}
      {truck.hours_until_deadline != null && (
        <div style={{ fontSize: 12, color: '#ffaa00', fontFamily: 'Courier New, monospace' }}>
          DEPARTS IN: {truck.hours_until_deadline}m
        </div>
      )}
    </div>
  )
}

export default function TruckLeaderboard({ demoTruck }) {
  const { rows: trucks } = useRealtimeTable('trucks', {
    orderBy: 'state_of_charge',
    orderAscending: true,
    refetchOnChanges: REFETCH_ON_EVENTS_INSERT,
  })
  const { rows: bays } = useRealtimeTable('bays', {
    refetchOnChanges: REFETCH_ON_EVENTS_INSERT,
  })

  // Show every truck (incl. at_port / Pier E) so balances stay visible — do not filter by status.
  const displayTrucks = demoTruck ? [demoTruck] : (trucks ?? [])

  return (
    <aside
      style={{
        width: 300,
        flexShrink: 0,
        background: '#0d1225',
        borderLeft: '1px solid #1a3a5c',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          color: '#00aaff',
          fontSize: 12,
          letterSpacing: 2,
          padding: '12px 14px',
          borderBottom: '1px solid #1a3a5c',
          flexShrink: 0,
          fontFamily: 'Courier New, monospace',
        }}
      >
        SWARM STATUS
      </div>
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 8,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
      >
        {displayTrucks.map((t) => (
          <TruckCard
            key={t.id}
            truck={t}
            baysRows={demoTruck ? [] : bays}
          />
        ))}
      </div>
    </aside>
  )
}
