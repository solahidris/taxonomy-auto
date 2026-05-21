import { useState, useEffect } from 'react'

type Niche = {
  id: string
  name: string
  description: string
  keywords: string[]
  video_count: number
  sample_titles: string[]
}

type Category = {
  id: string
  name: string
  description: string
  children: Niche[]
}

type Taxonomy = {
  version: string
  generated_at: string
  total_niches: number
  tree: Category[]
}

type Result = {
  id: string
  name: string
  description: string
  path: string[]
  keywords: string[]
  score: number
}

const PLACEHOLDERS = [
  'Morning calisthenics coach. Helping tall guys build strength without a gym. #calisthenics #bodyweight',
  'I cook 15-minute meals for busy parents. Meal prep every Sunday. #mealprep #easyrecipes',
  'Daily Hyrox training logs. Race prep tips for beginners. #hyrox #functionalfitness',
  'Thrift flipping & fashion hacks on a budget. Sustainable style. #thrift #ootd',
  'Indie game dev sharing my build in public. Pixel art + gamedev tutorials.',
]

export default function Home() {
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null)
  const [taxError, setTaxError] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [tab, setTab] = useState<'classify' | 'browse'>('classify')
  const [text, setText] = useState('')
  const [results, setResults] = useState<Result[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [placeholder] = useState(() => PLACEHOLDERS[Math.floor(Math.random() * PLACEHOLDERS.length)])

  useEffect(() => {
    fetch('/api/taxonomy')
      .then(r => r.json())
      .then(d => (d.error ? setTaxError(d.error) : setTaxonomy(d)))
      .catch(() => setTaxError('Failed to load taxonomy'))
  }, [])

  const classify = async () => {
    if (!text.trim() || loading) return
    setLoading(true)
    setError('')
    setResults([])
    try {
      const r = await fetch('/api/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      const d = await r.json()
      if (d.error) setError(d.error)
      else setResults(d.results)
    } catch {
      setError('Classification failed. Check the server logs.')
    }
    setLoading(false)
  }

  const toggle = (id: string) =>
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Creator Niche Taxonomy</h1>
            <p className="text-xs text-gray-500 mt-0.5">
              {taxonomy
                ? `${taxonomy.total_niches} niches across ${taxonomy.tree.length} categories · ${taxonomy.generated_at}`
                : 'Loading...'}
            </p>
          </div>
          <nav className="flex gap-1 bg-gray-900 rounded-lg p-1">
            {(['classify', 'browse'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all capitalize ${
                  tab === t ? 'bg-indigo-600 text-white shadow' : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {t}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        {/* Classify tab */}
        {tab === 'classify' && (
          <div className="max-w-2xl">
            <p className="text-sm text-gray-400 mb-5">
              Paste a creator bio, video caption, or hashtag list to find their niche in the taxonomy.
            </p>
            <textarea
              className="w-full h-32 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:border-indigo-500 placeholder-gray-600 transition-colors"
              placeholder={placeholder}
              value={text}
              onChange={e => setText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && e.metaKey && classify()}
            />
            <div className="flex items-center gap-3 mt-3">
              <button
                onClick={classify}
                disabled={loading || !text.trim()}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
              >
                {loading ? 'Classifying...' : 'Classify'}
              </button>
              <span className="text-xs text-gray-600">⌘ + Enter</span>
            </div>

            {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

            {results.length > 0 && (
              <div className="mt-7 space-y-3">
                <p className="text-xs text-gray-500 uppercase tracking-wider">Top matches</p>
                {results.map((r, i) => (
                  <div
                    key={r.id}
                    className={`rounded-xl border px-5 py-4 transition-all ${
                      i === 0
                        ? 'border-indigo-500 bg-indigo-950/40 shadow-lg shadow-indigo-950/30'
                        : 'border-gray-800 bg-gray-900/60'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-500 mb-1">{r.path.join(' › ')}</div>
                        <div className={`font-semibold text-sm ${i === 0 ? 'text-white' : 'text-gray-200'}`}>
                          {r.name}
                        </div>
                        <div className="text-xs text-gray-400 mt-1 leading-relaxed">{r.description}</div>
                        {r.keywords.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {r.keywords.map(k => (
                              <span
                                key={k}
                                className="text-xs bg-gray-800 text-gray-400 rounded-md px-1.5 py-0.5"
                              >
                                #{k}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="shrink-0 text-right">
                        <div className={`text-base font-bold tabular-nums ${i === 0 ? 'text-indigo-400' : 'text-gray-500'}`}>
                          {(r.score * 100).toFixed(1)}%
                        </div>
                        <div className="text-xs text-gray-600">match</div>
                      </div>
                    </div>
                    {i === 0 && (
                      <div className="mt-3 h-1 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 rounded-full transition-all duration-700"
                          style={{ width: `${r.score * 100}%` }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Browse tab */}
        {tab === 'browse' && (
          <div>
            {taxError ? (
              <div className="bg-gray-900 border border-dashed border-gray-700 rounded-xl p-8 text-center">
                <p className="text-gray-400 text-sm">{taxError}</p>
                <p className="text-gray-600 text-xs mt-2">Run the pipeline to generate the taxonomy.</p>
              </div>
            ) : !taxonomy ? (
              <p className="text-gray-500 text-sm">Loading taxonomy...</p>
            ) : (
              <div className="space-y-2">
                {taxonomy.tree.map(cat => (
                  <div key={cat.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                    <button
                      onClick={() => toggle(cat.id)}
                      className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-gray-800/50 transition-colors text-left"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium">{cat.name}</span>
                        <span className="text-xs text-gray-500 bg-gray-800 rounded px-2 py-0.5">
                          {cat.children.length} niches
                        </span>
                      </div>
                      <span className="text-gray-600 text-xs">{expanded.has(cat.id) ? '▲' : '▼'}</span>
                    </button>

                    {expanded.has(cat.id) && (
                      <div className="border-t border-gray-800">
                        {cat.children.map((niche, i) => (
                          <div
                            key={niche.id}
                            className={`px-5 py-3.5 ${i < cat.children.length - 1 ? 'border-b border-gray-800/60' : ''}`}
                          >
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-gray-100">{niche.name}</div>
                                <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">
                                  {niche.description}
                                </div>
                                {niche.keywords.length > 0 && (
                                  <div className="flex flex-wrap gap-1 mt-2">
                                    {niche.keywords.map(k => (
                                      <span key={k} className="text-xs bg-gray-800 text-gray-500 rounded px-1.5 py-0.5">
                                        #{k}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                              <span className="shrink-0 text-xs text-gray-600 tabular-nums">
                                {niche.video_count}v
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
