import { useEffect, useRef, useState } from 'react'
import supabase from '../lib/supabase'

/**
 * @param {string} tableName
 * @param {{
 *   filterColumn?: string
 *   filterValue?: string
 *   orderBy?: string
 *   orderAscending?: boolean
 *   limit?: number
 * }} [options]
 */
export default function useRealtimeTable(tableName, options = {}) {
  const filterColumn = options.filterColumn
  const filterValue = options.filterValue
  const orderBy = options.orderBy
  const orderAscending = options.orderAscending ?? false
  const limit = options.limit

  const channelNameRef = useRef(
    `realtime-${tableName}-${Date.now()}`
  )
  const channelRef = useRef(null)
  const [rows, setRows] = useState([])
  const [lastUpdated, setLastUpdated] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function fetchInitial() {
      let query = supabase.from(tableName).select('*')

      if (filterColumn != null && filterValue !== undefined) {
        query = query.eq(filterColumn, filterValue)
      }
      if (orderBy) {
        query = query.order(orderBy, { ascending: orderAscending })
      }
      if (typeof limit === 'number') {
        query = query.limit(limit)
      }

      const { data, error } = await query
      if (cancelled) return
      if (error) {
        const msg = String(error.message ?? error)
        const invalidKey = /invalid api key/i.test(msg)
        console.error(
          `[useRealtimeTable:${tableName}] REST error:`,
          msg,
          '| code:',
          error.code,
          '| details:',
          error.details,
          '| hint:',
          error.hint,
          invalidKey
            ? '\n→ Invalid or outdated anon key: copy **Project Settings → API → anon public** into `SUPABASE_ANON_KEY` in repo-root `.env`, restart `npm run dev`. (Agents use `SUPABASE_KEY`; the browser cannot.)'
            : '\n→ If 401/403: check anon key + RLS (SELECT allowed for anon on public.' +
                tableName +
                ').'
        )
        setRows([])
      } else {
        setRows(data ?? [])
      }
      setLastUpdated(Date.now())
    }

    fetchInitial()

    const ch = supabase
      .channel(channelNameRef.current)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: tableName },
        (payload) => {
          if (payload.eventType !== 'INSERT' && payload.eventType !== 'UPDATE') {
            return
          }
          const row = payload.new
          if (!row || row.id == null) return

          setRows((prev) => {
            const idx = prev.findIndex((r) => r.id === row.id)
            if (idx >= 0) {
              const next = [...prev]
              next[idx] = row
              return next
            }
            return [...prev, row]
          })
          setLastUpdated(Date.now())
        }
      )
      .subscribe((status, err) => {
        if (import.meta.env.DEV && status === 'CHANNEL_ERROR') {
          console.error(
            `[useRealtimeTable:${tableName}] Realtime subscribe failed:`,
            err?.message ?? err,
            '— enable Realtime for this table in Supabase → Database → Replication.'
          )
        }
      })

    channelRef.current = ch

    return () => {
      cancelled = true
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current)
        channelRef.current = null
      }
    }
  }, [
    tableName,
    filterColumn,
    filterValue,
    orderBy,
    orderAscending,
    limit,
  ])

  return { rows, lastUpdated }
}
