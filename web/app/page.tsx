'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { api, PipelineStatus, ThemeData, ReviewStats } from './lib/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Play, RefreshCw, Mail, Download, ChevronDown, ChevronUp,
  Zap, BarChart2, MessageSquare, Lightbulb, Shield,
  TrendingUp, Star, AlertCircle, CheckCircle2, Clock,
  Cpu, Layers, FileText, Send, Settings, X, ExternalLink
} from 'lucide-react'

// ── Phase meta ─────────────────────────────────────────────────────────────
const PHASES = [
  { key: 'phase1_scrape',   icon: <Layers size={14}/>,      label: 'Scraping Reviews',      desc: 'Fetching from Play Store' },
  { key: 'phase2a_themes',  icon: <Cpu size={14}/>,         label: 'Discovering Themes',    desc: 'Groq LLM analysis' },
  { key: 'phase2b_classify',icon: <BarChart2 size={14}/>,   label: 'Classifying Reviews',   desc: 'Batching with Groq' },
  { key: 'phase3_report',   icon: <FileText size={14}/>,    label: 'Generating Pulse',      desc: 'Gemini writing note' },
  { key: 'phase4_email',    icon: <Send size={14}/>,        label: 'Drafting Email',        desc: 'Building email draft' },
]

const THEME_ICONS: Record<string, React.ReactNode> = {
  app_performance: <Zap size={16}/>,
  ui_ux: <Layers size={16}/>,
  investment_features: <TrendingUp size={16}/>,
  customer_support: <MessageSquare size={16}/>,
  security_trust: <Shield size={16}/>,
}

function phaseIndex(key: string | null): number {
  return PHASES.findIndex(p => p.key === key)
}

// ── Main component ─────────────────────────────────────────────────────────
export default function Home() {
  // Config state
  const [weeks, setWeeks] = useState(10)
  const [maxReviews, setMaxReviews] = useState(1000)
  const [sendEmail, setSendEmail] = useState(false)
  const [recipient, setRecipient] = useState('')
  const [recipientName, setRecipientName] = useState('')
  const [useMock, setUseMock] = useState(false)
  const [showConfig, setShowConfig] = useState(false)

  // Pipeline state
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Data state
  const [pulseContent, setPulseContent] = useState<string | null>(null)
  const [pulseDate, setPulseDate] = useState<string | null>(null)
  const [themes, setThemes] = useState<ThemeData[]>([])
  const [reviewStats, setReviewStats] = useState<ReviewStats | null>(null)
  const [showEmail, setShowEmail] = useState(false)
  const [emlContent, setEmlContent] = useState<string | null>(null)
  const [apiConnected, setApiConnected] = useState<boolean | null>(null)

  const pollRef = useRef<NodeJS.Timeout | null>(null)

  // ── On mount: check API + load existing data ────────────────────────────
  useEffect(() => {
    checkApi()
    loadExistingData()
  }, [])

  async function checkApi() {
    try {
      await api.health()
      setApiConnected(true)
    } catch {
      setApiConnected(false)
    }
  }

  async function loadExistingData() {
    try {
      const [pulse, themesData, stats] = await Promise.allSettled([
        api.getLatestPulse(),
        api.getLatestThemes(),
        api.getReviewStats(),
      ])
      if (pulse.status === 'fulfilled') {
        setPulseContent(pulse.value.content)
        setPulseDate(pulse.value.date)
      }
      if (themesData.status === 'fulfilled') {
        setThemes(themesData.value.themes)
      }
      if (stats.status === 'fulfilled') {
        setReviewStats(stats.value)
      }
    } catch { /* no existing data yet */ }
  }

  // ── Polling ────────────────────────────────────────────────────────────
  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.getStatus()
        setStatus(s)
        if (s.status === 'done') {
          setIsRunning(false)
          stopPolling()
          loadExistingData()
          if (s.pulse_md) setPulseContent(s.pulse_md)
        } else if (s.status === 'error') {
          setIsRunning(false)
          setError(s.error || 'Pipeline failed')
          stopPolling()
        }
      } catch (e) { /* keep polling */ }
    }, 2000)
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }, [])

  useEffect(() => () => stopPolling(), [stopPolling])

  // ── Run pipeline ────────────────────────────────────────────────────────
  async function handleRun() {
    setError(null)
    setIsRunning(true)
    setStatus({ status: 'running', phase: 'starting', started_at: new Date().toISOString(), finished_at: null, error: null, pulse_md: null })
    try {
      await api.runPipeline({ weeks, max_reviews: maxReviews, send_email: sendEmail, recipient: recipient || undefined, recipient_name: recipientName || undefined, use_mock: useMock })
      startPolling()
    } catch (e: any) {
      setError(e.message)
      setIsRunning(false)
    }
  }

  async function handleViewEmail() {
    try {
      const eml = await api.getLatestEml()
      setEmlContent(eml.content)
      setShowEmail(true)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const currentPhaseIdx = status ? phaseIndex(status.phase) : -1

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Top Nav ── */}
      <nav className="border-b border-white/5 backdrop-blur-sm sticky top-0 z-50 bg-[#0b0f1a]/80">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #00d09c, #00b386)' }}>
              <BarChart2 size={14} className="text-white" />
            </div>
            <span className="font-display font-semibold text-white text-base tracking-tight">
              Groww Pulse
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full text-groww-500 border border-groww-500/30 bg-groww-500/10 font-mono">
              v1.0
            </span>
          </div>
          <div className="flex items-center gap-3">
            <ApiStatusBadge connected={apiConnected} />
            <button
              onClick={() => setShowConfig(v => !v)}
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-white/5"
            >
              <Settings size={13} />
              Config
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-10 w-full flex-1">
        {/* ── Hero ── */}
        <div className="mb-10 animate-fade-up">
          <h1 className="font-display text-4xl font-semibold text-white tracking-tight leading-tight mb-2">
            Weekly Review <span style={{ color: '#00d09c' }}>Pulse</span>
          </h1>
          <p className="text-gray-400 text-base max-w-xl">
            Turns Groww's Play Store reviews into a one-page insight brief — themes, user quotes, and action ideas — delivered to your inbox.
          </p>
        </div>

        {/* ── Config panel ── */}
        {showConfig && (
          <ConfigPanel
            weeks={weeks} setWeeks={setWeeks}
            maxReviews={maxReviews} setMaxReviews={setMaxReviews}
            sendEmail={sendEmail} setSendEmail={setSendEmail}
            recipient={recipient} setRecipient={setRecipient}
            recipientName={recipientName} setRecipientName={setRecipientName}
            useMock={useMock} setUseMock={setUseMock}
            onClose={() => setShowConfig(false)}
          />
        )}

        {/* ── Main grid ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left col: controls + themes + stats */}
          <div className="lg:col-span-1 flex flex-col gap-5">

            {/* Run card */}
            <div className="glass-card rounded-2xl p-5">
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-4">Pipeline</h2>

              <div className="flex flex-wrap gap-2 mb-4 text-xs">
                <ConfigChip label={`${weeks}w window`} />
                <ConfigChip label={`${maxReviews.toLocaleString()} reviews`} />
                {useMock && <ConfigChip label="mock data" accent />}
                {sendEmail && <ConfigChip label="send email" accent />}
              </div>

              <button
                onClick={handleRun}
                disabled={isRunning || apiConnected === false}
                className="btn-glow w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: isRunning ? 'rgba(0,208,156,0.2)' : 'linear-gradient(135deg, #00d09c, #00b386)' }}
              >
                {isRunning
                  ? <><LoadingDots /> Running pipeline…</>
                  : <><Play size={14} /> Run Pipeline</>
                }
              </button>

              {apiConnected === false && (
                <p className="mt-3 text-xs text-amber-400/80 flex items-center gap-1.5">
                  <AlertCircle size={12} /> Backend offline — start the API server
                </p>
              )}
            </div>

            {/* Phase progress */}
            {(isRunning || status?.status === 'done' || status?.status === 'error') && (
              <div className="glass-card rounded-2xl p-5 animate-fade-in">
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-4">Progress</h2>
                <div className="space-y-2.5">
                  {PHASES.map((p, i) => {
                    const done = status?.status === 'done' || i < currentPhaseIdx
                    const active = i === currentPhaseIdx && isRunning
                    const failed = status?.status === 'error' && i === currentPhaseIdx
                    return (
                      <PhaseRow key={p.key} phase={p} done={done} active={active} failed={failed} index={i} />
                    )
                  })}
                </div>
                {status?.status === 'done' && (
                  <p className="mt-4 text-xs text-groww-500 flex items-center gap-1.5">
                    <CheckCircle2 size={13} /> All phases complete!
                  </p>
                )}
                {status?.status === 'error' && (
                  <p className="mt-4 text-xs text-red-400 flex items-center gap-1.5">
                    <AlertCircle size={13} /> {status.error}
                  </p>
                )}
              </div>
            )}

            {/* Error banner */}
            {error && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400">
                <strong className="block mb-1">Error</strong>{error}
              </div>
            )}

            {/* Themes */}
            {themes.length > 0 && (
              <div className="glass-card rounded-2xl p-5 animate-fade-in">
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-4">Themes</h2>
                <div className="space-y-2">
                  {themes.map((t, i) => (
                    <ThemeBar key={t.id} theme={t} maxCount={themes[0].count} index={i} />
                  ))}
                </div>
              </div>
            )}

            {/* Review stats */}
            {reviewStats && (
              <div className="glass-card rounded-2xl p-5 animate-fade-in">
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-4">Review Stats</h2>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <StatBox label="Total Reviews" value={reviewStats.total.toLocaleString()} />
                  <StatBox label="Avg Rating" value={`${reviewStats.avgRating}★`} accent />
                  <StatBox label="Window" value={`${reviewStats.weeksRequested}w`} />
                  <StatBox label="Last Run" value={reviewStats.scrapedAt ? new Date(reviewStats.scrapedAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : '—'} />
                </div>
                <RatingBar distribution={reviewStats.ratingDistribution} total={reviewStats.total} />
              </div>
            )}

          </div>

          {/* Right col: pulse note */}
          <div className="lg:col-span-2 flex flex-col gap-5">

            {pulseContent ? (
              <div className="glass-card rounded-2xl overflow-hidden animate-fade-in">
                {/* Pulse header */}
                <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between"
                  style={{ background: 'linear-gradient(135deg, rgba(0,208,156,0.1), rgba(0,179,134,0.05))' }}>
                  <div>
                    <h2 className="font-display text-base font-semibold text-white">Weekly Pulse Note</h2>
                    {pulseDate && (
                      <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                        <Clock size={11} /> Week of {pulseDate}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleViewEmail}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg text-groww-500 border border-groww-500/30 hover:bg-groww-500/10 transition-colors"
                    >
                      <Mail size={12} /> Email Draft
                    </button>
                    <DownloadButton content={pulseContent} filename={`groww-pulse-${pulseDate}.md`} />
                  </div>
                </div>

                {/* Pulse body */}
                <div className="p-6">
                  <div className="prose-pulse max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {pulseContent}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyPulse isRunning={isRunning} />
            )}

          </div>
        </div>

        {/* ── Pipeline architecture diagram ── */}
        <ArchitectureDiagram />

      </main>

      {/* ── Email modal ── */}
      {showEmail && emlContent && (
        <EmailModal content={emlContent} onClose={() => setShowEmail(false)} />
      )}

      {/* ── Footer ── */}
      <footer className="border-t border-white/5 mt-16 py-6 text-center text-xs text-gray-600">
        Groww Review Pulse · Built for PM Milestone 3 · {new Date().getFullYear()}
      </footer>
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function ApiStatusBadge({ connected }: { connected: boolean | null }) {
  if (connected === null) return (
    <span className="flex items-center gap-1.5 text-xs text-gray-500">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-600 animate-pulse" />
      Checking API…
    </span>
  )
  return (
    <span className={`flex items-center gap-1.5 text-xs ${connected ? 'text-groww-500' : 'text-red-400'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-groww-500 shadow-[0_0_6px_#00d09c]' : 'bg-red-400'}`} />
      {connected ? 'API connected' : 'API offline'}
    </span>
  )
}

function ConfigChip({ label, accent }: { label: string; accent?: boolean }) {
  return (
    <span className={`px-2 py-1 rounded-md text-xs font-mono ${accent ? 'bg-groww-500/15 text-groww-500 border border-groww-500/25' : 'bg-white/5 text-gray-400 border border-white/10'}`}>
      {label}
    </span>
  )
}

function LoadingDots() {
  return (
    <span className="flex gap-1 items-center">
      {[0,1,2].map(i => (
        <span key={i} className="w-1 h-1 rounded-full bg-white" style={{ animation: `pulseDot 1.4s ease-in-out ${i * 0.16}s infinite` }} />
      ))}
    </span>
  )
}

function PhaseRow({ phase, done, active, failed, index }: { phase: typeof PHASES[0]; done: boolean; active: boolean; failed: boolean; index: number }) {
  const color = failed ? 'text-red-400' : done ? 'text-groww-500' : active ? 'text-white' : 'text-gray-600'
  const bg = failed ? 'bg-red-500/10 border-red-500/20' : done ? 'bg-groww-500/10 border-groww-500/20' : active ? 'bg-white/8 border-white/15' : 'bg-white/3 border-white/5'
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-lg border transition-all animate-slide-in step-${index} ${bg}`}>
      <span className={color}>{phase.icon}</span>
      <div className="flex-1 min-w-0">
        <p className={`text-xs font-medium truncate ${color}`}>{phase.label}</p>
        {active && <p className="text-xs text-gray-500 truncate">{phase.desc}</p>}
      </div>
      <span className="ml-auto flex-shrink-0">
        {done && <CheckCircle2 size={13} className="text-groww-500" />}
        {active && <RefreshCw size={13} className="text-gray-400 animate-spin" />}
        {failed && <AlertCircle size={13} className="text-red-400" />}
      </span>
    </div>
  )
}

function ThemeBar({ theme, maxCount, index }: { theme: ThemeData; maxCount: number; index: number }) {
  const pct = Math.round((theme.count / Math.max(maxCount, 1)) * 100)
  const icon = THEME_ICONS[theme.id] || <Star size={16} />
  return (
    <div className={`animate-fade-up step-${index}`}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-groww-500/70">{icon}</span>
          <span className="text-xs text-gray-300 font-medium">{theme.label}</span>
        </div>
        <span className="text-xs text-gray-500 font-mono">{theme.count}</span>
      </div>
      <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #00d09c, #00b386)' }}
        />
      </div>
    </div>
  )
}

function StatBox({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="bg-white/4 rounded-xl p-3 border border-white/5">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-base font-semibold font-mono ${accent ? 'text-groww-500' : 'text-white'}`}>{value}</p>
    </div>
  )
}

function RatingBar({ distribution, total }: { distribution: Record<string, number>; total: number }) {
  return (
    <div className="space-y-1.5">
      {[5,4,3,2,1].map(star => {
        const count = distribution[star] || 0
        const pct = Math.round((count / Math.max(total, 1)) * 100)
        return (
          <div key={star} className="flex items-center gap-2">
            <span className="text-xs text-gray-500 w-6 text-right font-mono">{star}★</span>
            <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${pct}%`,
                  background: star >= 4 ? '#00d09c' : star === 3 ? '#f59e0b' : '#ef4444',
                  opacity: 0.7 + star * 0.06,
                }}
              />
            </div>
            <span className="text-xs text-gray-600 font-mono w-8">{pct}%</span>
          </div>
        )
      })}
    </div>
  )
}

function DownloadButton({ content, filename }: { content: string; filename: string }) {
  function download() {
    const blob = new Blob([content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <button
      onClick={download}
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg text-gray-400 border border-white/10 hover:bg-white/5 hover:text-white transition-colors"
    >
      <Download size={12} /> .md
    </button>
  )
}

function EmptyPulse({ isRunning }: { isRunning: boolean }) {
  return (
    <div className="glass-card rounded-2xl flex flex-col items-center justify-center py-24 text-center px-8">
      {isRunning ? (
        <>
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4" style={{ background: 'rgba(0,208,156,0.1)' }}>
            <RefreshCw size={24} className="text-groww-500 animate-spin" />
          </div>
          <h3 className="text-white font-semibold mb-2">Pipeline running…</h3>
          <p className="text-gray-500 text-sm max-w-xs">Scraping reviews, discovering themes, and generating your pulse note.</p>
        </>
      ) : (
        <>
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4" style={{ background: 'rgba(255,255,255,0.04)' }}>
            <FileText size={24} className="text-gray-600" />
          </div>
          <h3 className="text-white font-semibold mb-2">No pulse yet</h3>
          <p className="text-gray-500 text-sm max-w-xs">Hit "Run Pipeline" to generate your first weekly insight note.</p>
        </>
      )}
    </div>
  )
}

function EmailModal({ content, onClose }: { content: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }}>
      <div className="glass-card rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden animate-fade-up">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
          <div className="flex items-center gap-2">
            <Mail size={16} className="text-groww-500" />
            <h3 className="font-semibold text-white text-sm">Email Draft (.eml)</h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/5">
            <X size={16} />
          </button>
        </div>
        <div className="overflow-auto flex-1 p-5">
          <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap leading-relaxed">{content}</pre>
        </div>
      </div>
    </div>
  )
}

function ConfigPanel({
  weeks, setWeeks, maxReviews, setMaxReviews,
  sendEmail, setSendEmail, recipient, setRecipient,
  recipientName, setRecipientName, useMock, setUseMock, onClose
}: any) {
  return (
    <div className="glass-card rounded-2xl p-6 mb-6 animate-fade-up border border-groww-500/20">
      <div className="flex items-center justify-between mb-5">
        <h2 className="font-semibold text-white flex items-center gap-2">
          <Settings size={15} className="text-groww-500" /> Pipeline Configuration
        </h2>
        <button onClick={onClose} className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/5">
          <X size={15} />
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        <div>
          <label className="block text-xs text-gray-400 mb-2">Review Window (weeks)</label>
          <input
            type="range" min={8} max={12} value={weeks}
            onChange={e => setWeeks(+e.target.value)}
            className="w-full accent-groww-500"
          />
          <p className="text-xs text-groww-500 font-mono mt-1">{weeks} weeks</p>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-2">Max Reviews</label>
          <select
            value={maxReviews}
            onChange={e => setMaxReviews(+e.target.value)}
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-groww-500/50"
          >
            {[200, 500, 1000, 2000, 5000].map(v => <option key={v} value={v}>{v.toLocaleString()}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-2">Recipient Email</label>
          <input
            type="email" value={recipient}
            onChange={e => setRecipient(e.target.value)}
            placeholder="you@example.com"
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-groww-500/50 placeholder:text-gray-600"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-2">Recipient Name</label>
          <input
            type="text" value={recipientName}
            onChange={e => setRecipientName(e.target.value)}
            placeholder="First name"
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-groww-500/50 placeholder:text-gray-600"
          />
        </div>
        <div className="flex flex-col gap-3 justify-center">
          <label className="flex items-center gap-3 cursor-pointer">
            <div
              onClick={() => setSendEmail((v: boolean) => !v)}
              className={`w-9 h-5 rounded-full transition-colors relative ${sendEmail ? 'bg-groww-600' : 'bg-white/10'}`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${sendEmail ? 'translate-x-4' : 'translate-x-0.5'}`} />
            </div>
            <span className="text-sm text-gray-300">Send email on completion</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <div
              onClick={() => setUseMock(v => !v)}
              className={`w-9 h-5 rounded-full transition-colors relative ${useMock ? 'bg-groww-600' : 'bg-white/10'}`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${useMock ? 'translate-x-4' : 'translate-x-0.5'}`} />
            </div>
            <span className="text-sm text-gray-300">Use mock data (no API keys needed)</span>
          </label>
        </div>
      </div>
    </div>
  )
}

function ArchitectureDiagram() {
  const [open, setOpen] = useState(false)
  const steps = [
    { icon: <Layers size={16}/>, title: 'Phase 1', sub: 'Play Store Scrape', color: '#6366f1' },
    { icon: <Cpu size={16}/>, title: 'Phase 2a', sub: 'Theme Discovery (Groq)', color: '#8b5cf6' },
    { icon: <BarChart2 size={16}/>, title: 'Phase 2b', sub: 'Classification (Groq)', color: '#a855f7' },
    { icon: <FileText size={16}/>, title: 'Phase 3', sub: 'Pulse Note (Gemini)', color: '#00d09c' },
    { icon: <Send size={16}/>, title: 'Phase 4', sub: 'Email Delivery', color: '#00b386' },
  ]
  return (
    <div className="mt-8">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
      >
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        Pipeline architecture
      </button>
      {open && (
        <div className="mt-4 glass-card rounded-2xl p-6 animate-fade-in">
          <div className="flex flex-wrap items-center gap-2 justify-center">
            {steps.map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="flex flex-col items-center gap-1 px-4 py-3 rounded-xl border border-white/8 bg-white/3">
                  <span style={{ color: s.color }}>{s.icon}</span>
                  <p className="text-xs font-semibold text-white">{s.title}</p>
                  <p className="text-xs text-gray-500 text-center max-w-[90px]">{s.sub}</p>
                </div>
                {i < steps.length - 1 && (
                  <span className="text-gray-600 text-lg">→</span>
                )}
              </div>
            ))}
          </div>
          <p className="text-center text-xs text-gray-600 mt-4">
            google-play-scraper → Groq (llama-3.3-70b) → Gemini (2.5-flash) → Gmail SMTP
          </p>
        </div>
      )}
    </div>
  )
}
