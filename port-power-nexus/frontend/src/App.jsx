import { useRef, useEffect, useState } from 'react';
import TerminalMap from './components/TerminalMap';
import useRealtimeTable from './hooks/useRealtimeTable';
import { effectiveMapStatus } from './lib/mapTruckStatus';

// ─── Shared card shell ────────────────────────────────────────────────────────
function Card({ style, children }) {
  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.92)',
        backdropFilter: 'blur(12px)',
        borderRadius: 12,
        border: '1px solid rgba(0,0,0,0.08)',
        boxShadow: '0 2px 16px rgba(0,0,0,0.10)',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ─── Top stat pill ────────────────────────────────────────────────────────────
function StatCard({ label, value, valueColor = '#111' }) {
  return (
    <Card style={{ padding: '10px 18px', minWidth: 110 }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1.5, color: '#9ca3af', marginBottom: 4, fontFamily: 'system-ui, sans-serif' }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: valueColor, fontFamily: 'system-ui, sans-serif', lineHeight: 1 }}>
        {value}
      </div>
    </Card>
  );
}

// ─── Stress bar variant ───────────────────────────────────────────────────────
function StressCard({ gridStress }) {
  let label = 'LOW';
  let color = '#16a34a';
  if (gridStress >= 0.8) { label = 'HIGH'; color = '#dc2626'; }
  else if (gridStress >= 0.5) { label = 'MEDIUM'; color = '#d97706'; }

  return (
    <Card style={{ padding: '10px 18px', minWidth: 140 }}>
      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1.5, color: '#9ca3af', marginBottom: 6, fontFamily: 'system-ui, sans-serif' }}>
        GRID STRESS
      </div>
      <div style={{ fontSize: 16, fontWeight: 700, color, fontFamily: 'system-ui, sans-serif', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ height: 5, background: '#f1f5f9', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${gridStress * 100}%`, background: color, borderRadius: 99, transition: 'width 0.6s ease' }} />
      </div>
    </Card>
  );
}

// ─── Live Bidding War sidebar ─────────────────────────────────────────────────
const PULSE_STYLE = `
  @keyframes bidPulse {
    0%   { background: rgba(245,158,11,0.18); }
    50%  { background: rgba(245,158,11,0.06); }
    100% { background: rgba(245,158,11,0.18); }
  }
`;

function BiddingPanel({ trucks, bays }) {
  const bidding = trucks.filter((t) => effectiveMapStatus(t, bays) === 'bidding');

  // Track previous current_bid per truck to detect changes
  const prevBidsRef = useRef({});
  const [pulsingIds, setPulsingIds] = useState(new Set());

  useEffect(() => {
    const prev = prevBidsRef.current;
    const changed = new Set();
    bidding.forEach((t) => {
      if (prev[t.id] !== undefined && prev[t.id] !== t.current_bid) {
        changed.add(t.id);
      }
      prev[t.id] = t.current_bid;
    });
    if (changed.size === 0) return;
    setPulsingIds((s) => new Set([...s, ...changed]));
    const timer = setTimeout(() => {
      setPulsingIds((s) => {
        const next = new Set(s);
        changed.forEach((id) => next.delete(id));
        return next;
      });
    }, 1200);
    return () => clearTimeout(timer);
  }, [bidding]);

  return (
    <Card style={{ width: 260, overflow: 'hidden' }}>
      <style>{PULSE_STYLE}</style>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px', borderBottom: '1px solid #f1f5f9' }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 6px #22c55e', flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, color: '#111', fontFamily: 'system-ui, sans-serif' }}>
          ACTIVE BIDDING WAR
        </span>
        <span style={{ fontSize: 9, color: '#22c55e', fontWeight: 700, marginLeft: 'auto', letterSpacing: 1, fontFamily: 'system-ui, sans-serif' }}>
          LIVE
        </span>
      </div>

      {/* Truck rows */}
      {bidding.length === 0 ? (
        <div style={{ padding: '16px', fontSize: 11, color: '#9ca3af', fontFamily: 'system-ui, sans-serif', textAlign: 'center' }}>
          No trucks currently bidding
        </div>
      ) : (
        bidding.map((truck) => {
          const soc = Math.round(truck.state_of_charge ?? 0);
          const bidPrice = truck.current_bid != null
            ? `$${Number(truck.current_bid).toFixed(2)}`
            : '—';
          const isPulsing = pulsingIds.has(truck.id);
          return (
            <div
              key={truck.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 16px',
                borderBottom: '1px solid #f8fafc',
                borderLeft: '3px solid #f59e0b',
                animation: isPulsing ? 'bidPulse 0.6s ease-in-out 2' : 'none',
              }}
            >
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#111', fontFamily: 'system-ui, sans-serif' }}>
                  {(truck.name ?? 'TRUCK').toUpperCase()}
                </div>
                <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 2, fontFamily: 'system-ui, sans-serif' }}>
                  SOC {soc}% · {soc >= 20 ? 'Threshold Met' : 'Critical'}
                </div>
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#16a34a', fontFamily: 'system-ui, sans-serif', transition: 'color 0.3s' }}>
                {bidPrice}
              </div>
            </div>
          );
        })
      )}
    </Card>
  );
}

// ─── Activity feed panel ──────────────────────────────────────────────────────
const EVENT_COLORS = {
  bid:            '#2563eb',
  win:            '#16a34a',
  signal:         '#7c3aed',
  payment:        '#d97706',
  auction_start:  '#0891b2',
  charge_complete:'#ca8a04',
  truck_reset:    '#059669',
  conversation:   '#6d28d9',
  chat:           '#6d28d9',
};

function ActivityFeed({ events }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  const reversed = [...events].reverse();

  return (
    <Card style={{ width: '100%', borderRadius: '12px 12px 0 0', border: 'none', borderTop: '1px solid rgba(0,0,0,0.06)', boxShadow: '0 -2px 16px rgba(0,0,0,0.07)' }}>
      <div style={{ padding: '6px 16px 4px', fontSize: 9, fontWeight: 700, letterSpacing: 1.5, color: '#9ca3af', fontFamily: 'system-ui, sans-serif', borderBottom: '1px solid #f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span>TERMINAL SWARM ACTIVITY</span>
        <span style={{ color: '#22c55e' }}>10_NODES_OK</span>
      </div>
      <div ref={scrollRef} style={{ height: 100, overflowY: 'auto', padding: '4px 16px 8px' }}>
        {reversed.map((event) => {
          const t = new Date(event.created_at).toLocaleTimeString('en-US', { hour12: false });
          const type = (event.type ?? '').toUpperCase();
          const color = EVENT_COLORS[event.type] ?? '#6b7280';
          return (
            <div key={event.id} style={{ fontSize: 10, lineHeight: 1.7, fontFamily: 'ui-monospace, Courier New, monospace', color, wordBreak: 'break-word' }}>
              <span style={{ color: '#9ca3af' }}>[{t}]</span> {type}: {event.message}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────
export default function App() {
  const { rows: powerBids } = useRealtimeTable('power_bids');
  const { rows: trucks }    = useRealtimeTable('trucks');
  const { rows: bays }      = useRealtimeTable('bays');
  const { rows: auctionRows } = useRealtimeTable('auction_state', {
    orderBy: 'started_at',
    orderAscending: false,
    limit: 1,
  });
  const { rows: events } = useRealtimeTable('events', {
    orderBy: 'created_at',
    orderAscending: false,
    limit: 80,
  });

  const auction = auctionRows[0] ?? {};
  const price = auction.current_price != null
    ? `$${Number(auction.current_price).toFixed(2)}`
    : '--';
  const gridStress   = Number(auction.grid_stress ?? 0);
  const renewablePct = Math.round(auction.renewable_pct ?? 0);

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden', background: '#dde3ed' }}>

      {/* ── Full-screen 3D scene ── */}
      <TerminalMap
        powerBids={powerBids}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      />

      {/* ── Top-left branding ── */}
      <Card style={{ position: 'absolute', top: 16, left: 16, padding: '10px 16px', zIndex: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: 2, color: '#111', fontFamily: 'system-ui, sans-serif' }}>
          PORT-POWER NEXUS
        </div>
        <div style={{ fontSize: 9, color: '#9ca3af', letterSpacing: 1, marginTop: 2, fontFamily: 'system-ui, sans-serif' }}>
          SWARM FLEET · {trucks.length} NODES ACTIVE
        </div>
      </Card>

      {/* ── Top-right stat cards ── */}
      <div style={{ position: 'absolute', top: 16, right: 16, display: 'flex', gap: 10, zIndex: 10 }}>
        <StatCard label="AUCTION PRICE" value={price} valueColor={price !== '--' ? '#16a34a' : '#9ca3af'} />
        <StressCard gridStress={gridStress} />
        <StatCard label="RENEWABLE" value={`${renewablePct}%`} valueColor="#16a34a" />
      </div>

      {/* ── Left bidding war panel ── */}
      <div style={{ position: 'absolute', top: 100, left: 16, zIndex: 10 }}>
        <BiddingPanel trucks={trucks} bays={bays} />
      </div>

      {/* ── Bottom activity feed ── */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10, pointerEvents: 'none' }}>
        <div style={{ pointerEvents: 'auto' }}>
          <ActivityFeed events={events} />
        </div>
      </div>

    </div>
  );
}