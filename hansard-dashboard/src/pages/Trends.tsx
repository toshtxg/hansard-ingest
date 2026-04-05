import { useState, useEffect, useMemo } from 'react'
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { Search, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useSupabaseRpc } from '@/hooks/useSupabaseRpc'
import { supabase } from '@/lib/supabase'
import type {
  TrendsVolume, ParliamentSummary, SittingIntensity, SpeakerDiversity,
  KeywordTrendPoint, KeywordSpeaker, KeywordSpeakerDetail,
} from '@/lib/types'
import { formatNumber, formatDate, sectionTypeLabel, hansardUrl } from '@/lib/utils'

const CHART_COLORS = ['#0d9488', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#10b981', '#6366f1']
const SECTION_TYPES = ['OS', 'OA', 'WA', 'WANA', 'BP', 'BI', 'WS']


function RainbowSpinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-14">
      <div
        className="w-10 h-10 rounded-full animate-spin"
        style={{
          background: 'conic-gradient(from 0deg, #ef4444, #f97316, #eab308, #22c55e, #06b6d4, #3b82f6, #8b5cf6, #ef4444)',
          WebkitMask: 'radial-gradient(farthest-side, transparent 62%, black 63%)',
          mask: 'radial-gradient(farthest-side, transparent 62%, black 63%)',
        }}
      />
      {label && <p className="text-sm text-gray-400">{label}</p>}
    </div>
  )
}

function IndeterminateBar() {
  return (
    <div className="relative h-0.5 bg-gray-100 overflow-hidden rounded-full">
      <div
        className="absolute top-0 bottom-0 rounded-full"
        style={{
          background: 'linear-gradient(90deg, transparent, #0d9488, transparent)',
          animation: 'slide-indeterminate 1.4s ease-in-out infinite',
        }}
      />
    </div>
  )
}

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="text-center p-6 bg-red-50 rounded-lg">
      <p className="text-red-600 mb-2">{message}</p>
      <button onClick={onRetry} className="text-teal hover:underline text-sm">Retry</button>
    </div>
  )
}

export function Trends() {
  // ── Keyword section ────────────────────────────────────────────
  const [inputValue, setInputValue] = useState('')
  const [committedKeyword, setCommittedKeyword] = useState('')
  const [kwGranularity, setKwGranularity] = useState<'year' | 'quarter'>('year')
  const [trendsData, setTrendsData] = useState<KeywordTrendPoint[] | null>(null)
  const [trendsLoading, setTrendsLoading] = useState(false)
  const [speakers, setSpeakers] = useState<KeywordSpeaker[] | null>(null)
  const [speakersLoading, setSpeakersLoading] = useState(false)
  const [kwError, setKwError] = useState<string | null>(null)
  const [expandedSpeaker, setExpandedSpeaker] = useState<string | null>(null)
  const [speakerDetail, setSpeakerDetail] = useState<KeywordSpeakerDetail[] | null>(null)
  const [speakerDetailLoading, setSpeakerDetailLoading] = useState(false)

  useEffect(() => {
    if (!committedKeyword.trim()) {
      setTrendsData(null)
      setSpeakers(null)
      setExpandedSpeaker(null)
      setSpeakerDetail(null)
      setKwError(null)
      return
    }
    setTrendsLoading(true)
    setSpeakersLoading(true)
    setKwError(null)
    setExpandedSpeaker(null)
    setSpeakerDetail(null)

    supabase
      .rpc('keyword_trends_over_time', { p_keyword: committedKeyword, p_granularity: kwGranularity })
      .then(({ data, error }) => {
        if (error) setKwError(error.message)
        else setTrendsData((data as KeywordTrendPoint[]) ?? [])
        setTrendsLoading(false)
      })

    supabase
      .rpc('keyword_top_speakers', { p_keyword: committedKeyword, p_limit: 20 })
      .then(({ data, error }) => {
        if (error) setKwError(error.message)
        else setSpeakers((data as KeywordSpeaker[]) ?? [])
        setSpeakersLoading(false)
      })
  }, [committedKeyword, kwGranularity])

  function handleSearch() {
    const trimmed = inputValue.trim()
    if (trimmed) setCommittedKeyword(trimmed)
  }

  async function loadSpeakerDetail(mpName: string) {
    if (expandedSpeaker === mpName) {
      setExpandedSpeaker(null)
      setSpeakerDetail(null)
      return
    }
    setExpandedSpeaker(mpName)
    setSpeakerDetail(null)
    setSpeakerDetailLoading(true)
    const { data, error } = await supabase.rpc('keyword_speaker_breakdown', {
      p_keyword: committedKeyword,
      p_mp_name: mpName,
    })
    setSpeakerDetailLoading(false)
    if (error) setKwError(error.message)
    else if (data) setSpeakerDetail(data as KeywordSpeakerDetail[])
  }

  const hasKeyword = committedKeyword.trim().length > 0

  // ── Parliamentary overview ─────────────────────────────────────
  const [volumeGranularity, setVolumeGranularity] = useState<'year' | 'quarter'>('year')

  const { data: volumeRaw, loading: volumeLoading, error: volumeError, refetch: refetchVolume } =
    useSupabaseRpc<TrendsVolume[]>(
      'trends_volume_over_time',
      { p_granularity: volumeGranularity },
      [volumeGranularity]
    )

  const { data: parliaments, loading: parlLoading, error: parlError, refetch: refetchParl } =
    useSupabaseRpc<ParliamentSummary[]>('trends_parliament_summary')

  const { data: intensity, loading: intensityLoading, error: intensityError, refetch: refetchIntensity } =
    useSupabaseRpc<SittingIntensity[]>('trends_sitting_intensity', { p_granularity: 'year' })

  const { data: diversity, loading: diversityLoading, error: diversityError, refetch: refetchDiversity } =
    useSupabaseRpc<SpeakerDiversity[]>('trends_speaker_diversity', { p_granularity: 'year' })

  const volumePivoted = useMemo(() => {
    if (!volumeRaw) return []
    const periods = [...new Set(volumeRaw.map(r => r.period))].sort()
    return periods.map(period => {
      const row: Record<string, string | number> = { period }
      for (const type of SECTION_TYPES) {
        const match = volumeRaw.find(r => r.period === period && r.section_type === type)
        row[type] = match?.word_count ?? 0
      }
      return row
    })
  }, [volumeRaw])

  const activeSectionTypes = useMemo(() => {
    if (!volumeRaw) return []
    return SECTION_TYPES.filter(type => volumeRaw.some(r => r.section_type === type && (r.word_count ?? 0) > 0))
  }, [volumeRaw])

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-navy mb-1">Trends</h1>
        <p className="text-gray-600 text-sm">
          Track how topics evolve over time and explore overall parliamentary activity.
        </p>
      </div>

      {/* ── Keyword section ── */}
      <div className="space-y-6">
        <form
          onSubmit={e => { e.preventDefault(); handleSearch() }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Enter a keyword and press Search…"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              className="pl-9"
            />
          </div>
          <Button type="submit" disabled={!inputValue.trim()} className="shrink-0">
            Search
          </Button>
        </form>

        {kwError && (
          <div className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
            Search error: {kwError}. Check that the <code className="font-mono text-xs">keyword_matches</code> SQL function was created successfully in Supabase.
          </div>
        )}

        {hasKeyword && (trendsLoading || speakersLoading) && <IndeterminateBar />}

        {hasKeyword && (
          <>
            {/* Mentions over time chart */}
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle>Mentions over time</CardTitle>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Speeches and sittings referencing "{committedKeyword}"
                    </p>
                  </div>
                  <div className="flex rounded-md border overflow-hidden">
                    <button
                      onClick={() => setKwGranularity('year')}
                      className={`px-3 py-1.5 text-xs font-medium transition-colors ${kwGranularity === 'year' ? 'bg-teal text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                    >
                      Year
                    </button>
                    <button
                      onClick={() => setKwGranularity('quarter')}
                      className={`px-3 py-1.5 text-xs font-medium transition-colors ${kwGranularity === 'quarter' ? 'bg-teal text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                    >
                      Quarter
                    </button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {trendsLoading ? (
                  <RainbowSpinner label="Searching Hansard records…" />
                ) : !trendsData || trendsData.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-12">
                    No results found for "{committedKeyword}"
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={trendsData} margin={{ top: 10, right: 40, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                      <YAxis yAxisId="left" tick={{ fontSize: 11 }} width={40} allowDecimals={false} />
                      <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} width={40} allowDecimals={false} />
                      <Tooltip />
                      <Legend />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="speech_count"
                        stroke="#0d9488"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        name="Speeches"
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="sitting_count"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        name="Sittings"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            {/* Top speakers */}
            <Card>
              <CardHeader>
                <CardTitle>Who talks about it most</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {speakersLoading ? (
                  <RainbowSpinner label="Finding top speakers…" />
                ) : !speakers || speakers.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-8">No speakers found.</p>
                ) : (
                  <div className="divide-y">
                    {speakers.map((sp, idx) => {
                      const isExpanded = expandedSpeaker === sp.mp_name
                      return (
                        <div key={sp.mp_name}>
                          <button
                            onClick={() => loadSpeakerDetail(sp.mp_name)}
                            className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors text-left"
                          >
                            <span className="text-xs text-gray-400 w-5 tabular-nums text-right shrink-0">
                              {idx + 1}
                            </span>
                            <span className="flex-1 font-medium text-sm text-navy truncate">
                              {sp.mp_name}
                            </span>
                            <span className="text-xs text-gray-500 shrink-0">
                              {formatNumber(sp.speech_count)} speech{sp.speech_count !== 1 ? 'es' : ''}
                            </span>
                            <span className="text-xs text-gray-400 shrink-0">
                              {formatNumber(sp.sitting_count)} sitting{sp.sitting_count !== 1 ? 's' : ''}
                            </span>
                            {isExpanded
                              ? <ChevronDown size={14} className="text-gray-400 shrink-0" />
                              : <ChevronRight size={14} className="text-gray-400 shrink-0" />
                            }
                          </button>

                          {isExpanded && (
                            <div className="px-4 pb-3 bg-gray-50 border-t">
                              {speakerDetailLoading ? (
                                <div className="space-y-2 pt-3">
                                  {Array.from({ length: 3 }).map((_, i) => (
                                    <div key={i} className="h-8 bg-gray-200 animate-pulse rounded" />
                                  ))}
                                </div>
                              ) : speakerDetail && speakerDetail.length > 0 ? (
                                <table className="w-full text-xs mt-3">
                                  <thead>
                                    <tr className="text-gray-500 border-b">
                                      <th className="pb-1.5 text-left font-medium pr-3">Date</th>
                                      <th className="pb-1.5 text-left font-medium">Topic</th>
                                      <th className="pb-1.5 text-right font-medium pl-3">Times spoken</th>
                                      <th className="pb-1.5 text-right font-medium pl-3">Words</th>
                                      <th className="pb-1.5 pl-3"></th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {speakerDetail.map((row, i) => (
                                      <tr key={i} className="border-b border-gray-100">
                                        <td className="py-1.5 text-gray-500 whitespace-nowrap pr-3">
                                          {formatDate(row.sitting_date)}
                                        </td>
                                        <td className="py-1.5 text-gray-700">
                                          <span className="line-clamp-2">{row.discussion_title}</span>
                                          {row.one_liner && (
                                            <p className="text-gray-400 italic mt-0.5 line-clamp-2">{row.one_liner}</p>
                                          )}
                                        </td>
                                        <td className="py-1.5 text-right tabular-nums pl-3">
                                          {row.times_spoken}
                                        </td>
                                        <td className="py-1.5 text-right tabular-nums text-gray-500 pl-3">
                                          {formatNumber(row.word_count)}
                                        </td>
                                        <td className="py-1.5 pl-3">
                                          <a
                                            href={hansardUrl(row.sitting_date)}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex items-center gap-1 text-teal hover:underline whitespace-nowrap"
                                            onClick={e => e.stopPropagation()}
                                          >
                                            <ExternalLink size={11} /> Hansard
                                          </a>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              ) : (
                                <p className="text-xs text-gray-400 py-3">No detail available.</p>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* ── Parliamentary Overview ── */}
      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-navy">Parliamentary Overview</h2>

        {/* Volume Over Time */}
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle>Volume Over Time</CardTitle>
              <div className="flex rounded-md border overflow-hidden">
                <button
                  onClick={() => setVolumeGranularity('year')}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${volumeGranularity === 'year' ? 'bg-teal text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                >
                  Year
                </button>
                <button
                  onClick={() => setVolumeGranularity('quarter')}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${volumeGranularity === 'quarter' ? 'bg-teal text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                >
                  Quarter
                </button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {volumeLoading ? (
              <div className="h-72 bg-gray-100 animate-pulse rounded" />
            ) : volumeError ? (
              <ErrorCard message={`Failed to load volume data: ${volumeError}`} onRetry={refetchVolume} />
            ) : (
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={volumePivoted} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} width={65} tickFormatter={v => formatNumber(v as number)} />
                  <Tooltip formatter={(v) => formatNumber(v as number)} />
                  <Legend formatter={value => <span className="text-xs">{sectionTypeLabel(value)}</span>} />
                  {activeSectionTypes.map((type, index) => (
                    <Area
                      key={type}
                      type="monotone"
                      dataKey={type}
                      stackId="1"
                      stroke={CHART_COLORS[index % CHART_COLORS.length]}
                      fill={CHART_COLORS[index % CHART_COLORS.length]}
                      fillOpacity={0.8}
                      name={sectionTypeLabel(type)}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Parliament Comparison */}
        <section>
          <h3 className="text-base font-semibold text-navy mb-4">Parliament Comparison</h3>
          {parlLoading ? (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Card key={i}>
                  <CardContent className="pt-6 space-y-3">
                    {Array.from({ length: 4 }).map((_, j) => (
                      <div key={j} className="h-4 bg-gray-200 animate-pulse rounded" />
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : parlError ? (
            <ErrorCard message={`Failed to load parliament data: ${parlError}`} onRetry={refetchParl} />
          ) : (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {(parliaments ?? []).map(parl => (
                <Card key={parl.parliament_no}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">Parliament {parl.parliament_no}</CardTitle>
                    <p className="text-xs text-gray-500">{parl.date_range}</p>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Sittings</span>
                      <span className="font-medium tabular-nums">{formatNumber(parl.total_sittings)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Speeches</span>
                      <span className="font-medium tabular-nums">{formatNumber(parl.total_speeches)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Speakers</span>
                      <span className="font-medium tabular-nums">{formatNumber(parl.total_speakers)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Avg speeches/sitting</span>
                      <span className="font-medium tabular-nums">
                        {parl.avg_speeches_per_sitting != null ? parl.avg_speeches_per_sitting.toFixed(1) : '—'}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>

        {/* Sitting Intensity */}
        <Card>
          <CardHeader>
            <CardTitle>Sitting Intensity</CardTitle>
          </CardHeader>
          <CardContent>
            {intensityLoading ? (
              <div className="h-64 bg-gray-100 animate-pulse rounded" />
            ) : intensityError ? (
              <ErrorCard message={`Failed to load intensity data: ${intensityError}`} onRetry={refetchIntensity} />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={intensity ?? []} margin={{ top: 10, right: 40, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="left" tick={{ fontSize: 11 }} width={50} />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 11 }}
                    width={65}
                    tickFormatter={v => formatNumber(v as number)}
                  />
                  <Tooltip formatter={(v, name) => [formatNumber(v as number), name as string]} />
                  <Legend />
                  <Bar yAxisId="left" dataKey="sitting_count" fill="#0d9488" name="Sittings" radius={[3, 3, 0, 0]} />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="avg_words_per_sitting"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Avg Words/Sitting"
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Speaker Diversity */}
        <Card>
          <CardHeader>
            <CardTitle>Speaker Diversity</CardTitle>
          </CardHeader>
          <CardContent>
            {diversityLoading ? (
              <div className="h-64 bg-gray-100 animate-pulse rounded" />
            ) : diversityError ? (
              <ErrorCard message={`Failed to load diversity data: ${diversityError}`} onRetry={refetchDiversity} />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={diversity ?? []} margin={{ top: 10, right: 40, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="left" tick={{ fontSize: 11 }} width={50} />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 11 }}
                    width={65}
                    tickFormatter={v => formatNumber(v as number)}
                  />
                  <Tooltip formatter={(v, name) => [formatNumber(v as number), name as string]} />
                  <Legend />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="unique_speakers"
                    stroke="#0d9488"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Unique Speakers"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="avg_words_per_speaker"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Avg Words/Speaker"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
