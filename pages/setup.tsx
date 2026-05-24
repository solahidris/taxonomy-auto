import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'

type SetupStatus = {
  keys: { youtube: boolean; openai: boolean }
  taxonomy: { ready: boolean; stats: { total_niches: number; total_categories: number; total_videos: number } | null }
  ready: boolean
}

type LogLine = { type: 'start' | 'log' | 'done' | 'error'; text?: string; cmd?: string; code?: number; success?: boolean }

const STEPS = [
  { n: 1, label: 'Collect YouTube Shorts', desc: 'Round-robin across 15 categories', time: '~10 min', cost: 'Free' },
  { n: 2, label: 'Combine Datasets', desc: 'Merge V5 + new YouTube into 10K corpus', time: '~5 sec', cost: 'Free' },
  { n: 3, label: 'Generate Embeddings', desc: 'text-embedding-3-small for all videos', time: '~5 min', cost: '~$0.014' },
  { n: 4, label: 'Cluster Videos', desc: '4-level K-Means + HDBSCAN hierarchy', time: '~2 min', cost: 'Free' },
  { n: 5, label: 'Name Niches', desc: 'GPT-4o-mini names all 542 niches', time: '~3 min', cost: '~$0.30' },
  { n: 6, label: 'Evaluate Taxonomy', desc: 'Coverage, Gini, balance scores', time: '~5 sec', cost: 'Free' },
]

export default function Setup() {
  const [status, setStatus] = useState<SetupStatus | null>(null)
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)
  const [failed, setFailed] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [activeStep, setActiveStep] = useState<number | null>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)

  const fetchStatus = async () => {
    const r = await fetch('/api/setup/status')
    const d = await r.json()
    setStatus(d)
    if (d.taxonomy.ready) setDone(true)
  }

  useEffect(() => {
    fetchStatus()
    return () => esRef.current?.close()
  }, [])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  const runPipeline = (step?: number) => {
    if (running) return
    setRunning(true)
    setDone(false)
    setFailed(false)
    setLogs([])
    setActiveStep(step ?? null)

    const url = step ? `/api/pipeline/run?step=${step}` : '/api/pipeline/run'
    const es = new EventSource(url)
    esRef.current = es

    // EventSource only supports GET; use fetch + ReadableStream for POST
    es.close()
    esRef.current = null

    fetch(step ? `/api/pipeline/run?step=${step}` : '/api/pipeline/run', { method: 'POST' })
      .then(async res => {
        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done: streamDone, value } = await reader.read()
          if (streamDone) break

          buffer += decoder.decode(value, { stream: true })
          const parts = buffer.split('\n\n')
          buffer = parts.pop() || ''

          for (const part of parts) {
            const line = part.replace(/^data: /, '').trim()
            if (!line) continue
            try {
              const event: LogLine = JSON.parse(line)
              if (event.type === 'log' && event.text) {
                setLogs(prev => [...prev, event.text!])
              } else if (event.type === 'start') {
                setLogs(prev => [...prev, `▶ Running: ${event.cmd}`])
              } else if (event.type === 'done') {
                if (event.success) {
                  setLogs(prev => [...prev, '✓ Completed successfully'])
                  setDone(true)
                  fetchStatus()
                } else {
                  setLogs(prev => [...prev, `✗ Exited with code ${event.code}`])
                  setFailed(true)
                }
              } else if (event.type === 'error') {
                setLogs(prev => [...prev, `✗ Error: ${event.text}`])
                setFailed(true)
              }
            } catch {}
          }
        }
      })
      .catch(err => {
        setLogs(prev => [...prev, `✗ Connection error: ${err.message}`])
        setFailed(true)
      })
      .finally(() => {
        setRunning(false)
        setActiveStep(null)
      })
  }

  const allKeysOk = status?.keys.youtube && status?.keys.openai

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Creator Niche Taxonomy — Setup</h1>
            <p className="text-xs text-gray-500 mt-0.5">Get the pipeline running in one click</p>
          </div>
          <Link
            href="/"
            className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            ← Back to App
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10 space-y-8">
        {/* Status Cards */}
        <section>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">System Status</h2>
          <div className="grid grid-cols-3 gap-4">
            {[
              {
                label: 'YouTube API Key',
                ok: status?.keys.youtube,
                hint: 'Set YOUTUBE_API_KEY in .env.local',
                link: 'https://console.cloud.google.com',
                linkText: 'Get key →',
              },
              {
                label: 'OpenAI API Key',
                ok: status?.keys.openai,
                hint: 'Set OPENAI_API_KEY in .env.local',
                link: 'https://platform.openai.com/api-keys',
                linkText: 'Get key →',
              },
              {
                label: 'V6 Taxonomy',
                ok: status?.taxonomy.ready,
                hint: status?.taxonomy.ready
                  ? `${status.taxonomy.stats?.total_niches} niches · ${status.taxonomy.stats?.total_videos?.toLocaleString()} videos`
                  : 'Not generated yet — run pipeline below',
              },
            ].map(s => (
              <div
                key={s.label}
                className={`rounded-xl p-4 border ${
                  s.ok === undefined
                    ? 'bg-gray-900 border-gray-800'
                    : s.ok
                    ? 'bg-emerald-950/30 border-emerald-800/50'
                    : 'bg-red-950/30 border-red-800/50'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-lg ${
                    s.ok === undefined ? 'opacity-30' : s.ok ? 'text-emerald-400' : 'text-red-400'
                  }`}>
                    {s.ok === undefined ? '○' : s.ok ? '✓' : '✗'}
                  </span>
                  <span className="text-sm font-medium text-gray-200">{s.label}</span>
                </div>
                <p className="text-xs text-gray-500">{s.hint}</p>
                {!s.ok && s.link && (
                  <a
                    href={s.link}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-violet-400 hover:text-violet-300 mt-1 inline-block"
                  >
                    {s.linkText}
                  </a>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* .env.local Instructions */}
        {!allKeysOk && (
          <section className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Set up your API keys</h3>
            <p className="text-xs text-gray-500 mb-3">Create a <code className="text-violet-400">.env.local</code> file in the project root:</p>
            <pre className="bg-gray-950 border border-gray-800 rounded-lg p-4 text-xs text-gray-300 font-mono overflow-x-auto">
{`YOUTUBE_API_KEY=your_youtube_data_api_v3_key
OPENAI_API_KEY=your_openai_api_key`}
            </pre>
            <p className="text-xs text-gray-600 mt-3">Then restart the dev server: <code className="text-gray-400">npm run dev</code></p>
          </section>
        )}

        {/* Pipeline Runner */}
        <section>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Generate Taxonomy</h2>
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            {/* Full run button */}
            <div className="p-5 border-b border-gray-800 flex items-center justify-between gap-4">
              <div>
                <div className="text-sm font-semibold text-white mb-1">Run Full Pipeline</div>
                <div className="text-xs text-gray-500">All 6 steps · ~20 min · ~$0.31 total</div>
              </div>
              <button
                onClick={() => runPipeline()}
                disabled={running || !allKeysOk}
                className={`px-6 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                  running
                    ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                    : !allKeysOk
                    ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
                    : 'bg-violet-600 text-white hover:bg-violet-500'
                }`}
              >
                {running && activeStep === null ? 'Running...' : 'Run Pipeline'}
              </button>
            </div>

            {/* Individual steps */}
            <div className="divide-y divide-gray-800">
              {STEPS.map(s => (
                <div key={s.n} className="px-5 py-3 flex items-center gap-4">
                  <span className="text-xs text-gray-600 font-mono w-6 shrink-0">{s.n}</span>
                  <div className="flex-1">
                    <div className="text-sm text-gray-300">{s.label}</div>
                    <div className="text-xs text-gray-600">{s.desc}</div>
                  </div>
                  <div className="text-xs text-gray-600 w-16 text-right">{s.time}</div>
                  <div className="text-xs text-gray-600 w-14 text-right">{s.cost}</div>
                  <button
                    onClick={() => runPipeline(s.n)}
                    disabled={running || !allKeysOk}
                    className={`text-xs px-3 py-1 rounded-md transition-all shrink-0 ${
                      running && activeStep === s.n
                        ? 'bg-violet-800 text-violet-200'
                        : running || !allKeysOk
                        ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
                        : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                    }`}
                  >
                    {running && activeStep === s.n ? 'Running…' : 'Run'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Live Log */}
        {logs.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Live Output</h2>
              {running && (
                <span className="text-xs text-violet-400 animate-pulse">● Running</span>
              )}
              {done && !running && (
                <span className="text-xs text-emerald-400">● Complete</span>
              )}
              {failed && !running && (
                <span className="text-xs text-red-400">● Failed</span>
              )}
            </div>
            <div
              ref={logRef}
              className="bg-gray-950 border border-gray-800 rounded-xl p-4 h-72 overflow-y-auto font-mono text-xs text-gray-400 space-y-0.5"
            >
              {logs.map((line, i) => (
                <div
                  key={i}
                  className={
                    line.startsWith('✓') ? 'text-emerald-400' :
                    line.startsWith('✗') ? 'text-red-400' :
                    line.startsWith('▶') ? 'text-violet-400' :
                    'text-gray-400'
                  }
                >
                  {line}
                </div>
              ))}
              {running && <div className="text-gray-600 animate-pulse">▌</div>}
            </div>
            {!running && logs.length > 0 && (
              <button
                onClick={() => setLogs([])}
                className="text-xs text-gray-600 hover:text-gray-400 mt-2 transition-colors"
              >
                Clear log
              </button>
            )}
          </section>
        )}

        {/* Success CTA */}
        {done && status?.taxonomy.ready && (
          <section className="bg-emerald-950/30 border border-emerald-800/50 rounded-xl p-6 text-center">
            <div className="text-2xl mb-2">✓</div>
            <h3 className="text-base font-semibold text-emerald-200 mb-1">Taxonomy Ready</h3>
            <p className="text-sm text-emerald-200/70 mb-4">
              {status.taxonomy.stats?.total_niches} niches across {status.taxonomy.stats?.total_categories} categories ·{' '}
              {status.taxonomy.stats?.total_videos?.toLocaleString()} videos indexed
            </p>
            <Link
              href="/?v=v6"
              className="inline-block bg-emerald-600 text-white px-6 py-2.5 rounded-lg text-sm font-semibold hover:bg-emerald-500 transition-colors"
            >
              Open Classifier →
            </Link>
          </section>
        )}
      </main>
    </div>
  )
}
