import { useState, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, ChevronUp, ChevronDown } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { useSupabaseRpc } from '@/hooks/useSupabaseRpc'
import type { MPListItem } from '@/lib/types'
import { formatNumber, sectionTypeLabel } from '@/lib/utils'

type SortKey = keyof MPListItem
type SortDir = 'asc' | 'desc'

function useDebounce(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

export function MPList() {
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('total_words')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const { data, loading, error, refetch } = useSupabaseRpc<MPListItem[]>('mp_list')
  const debouncedSearch = useDebounce(search, 300)
  const navigate = useNavigate()

  const filtered = useMemo(() => {
    if (!data) return []
    const q = debouncedSearch.toLowerCase().trim()
    const rows = q ? data.filter(mp => mp.mp_name.toLowerCase().includes(q)) : data
    return [...rows].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }
      const an = av as number
      const bn = bv as number
      return sortDir === 'asc' ? an - bn : bn - an
    })
  }, [data, debouncedSearch, sortKey, sortDir])

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (col !== sortKey) return <ChevronDown className="h-3 w-3 opacity-30" />
    return sortDir === 'asc' ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
  }

  const cols: { key: SortKey; label: string; align: string }[] = [
    { key: 'mp_name', label: 'Name', align: 'text-left' },
    { key: 'total_words', label: 'Total Words', align: 'text-right' },
    { key: 'total_speeches', label: 'Speeches', align: 'text-right' },
    { key: 'sittings_active', label: 'Sittings', align: 'text-right' },
    { key: 'primary_section_type', label: 'Primary Type', align: 'text-left' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-navy mb-1">Members of Parliament</h1>
        <p className="text-gray-600 text-sm">
          Browse all MPs and their parliamentary activity. Click a row to see details.
        </p>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input
          placeholder="Search MPs..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {error ? (
        <div className="text-center p-6 bg-red-50 rounded-lg">
          <p className="text-red-600 mb-2">Failed to load MP list: {error}</p>
          <button onClick={refetch} className="text-teal hover:underline text-sm">
            Retry
          </button>
        </div>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  {cols.map(col => (
                    <th
                      key={col.key}
                      onClick={() => handleSort(col.key)}
                      className={`p-4 font-medium text-gray-600 cursor-pointer hover:text-navy select-none ${col.align}`}
                    >
                      <span className="inline-flex items-center gap-1">
                        {col.label}
                        <SortIcon col={col.key} />
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 10 }).map((_, i) => (
                      <tr key={i} className="border-b">
                        {cols.map(col => (
                          <td key={col.key} className="p-4">
                            <div className="h-4 bg-gray-200 animate-pulse rounded w-3/4" />
                          </td>
                        ))}
                      </tr>
                    ))
                  : filtered.map(mp => (
                      <tr
                        key={mp.mp_name}
                        onClick={() => navigate(`/mp/${encodeURIComponent(mp.mp_name)}`)}
                        className="border-b hover:bg-gray-50 cursor-pointer transition-colors"
                      >
                        <td className="p-4 font-medium text-navy">{mp.mp_name}</td>
                        <td className="p-4 text-right tabular-nums">{formatNumber(mp.total_words)}</td>
                        <td className="p-4 text-right tabular-nums">{formatNumber(mp.total_speeches)}</td>
                        <td className="p-4 text-right tabular-nums">{formatNumber(mp.sittings_active)}</td>
                        <td className="p-4">
                          <Badge variant="secondary">{sectionTypeLabel(mp.primary_section_type)}</Badge>
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
          {!loading && (
            <div className="px-4 py-3 border-t text-sm text-gray-500 bg-gray-50">
              {filtered.length} MP{filtered.length !== 1 ? 's' : ''} shown
              {debouncedSearch ? ` matching "${debouncedSearch}"` : ''}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
