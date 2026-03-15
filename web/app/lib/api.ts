const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface RunRequest {
  weeks: number
  max_reviews: number
  send_email: boolean
  recipient?: string
  recipient_name?: string
  use_mock?: boolean
}

export interface PipelineStatus {
  status: 'idle' | 'running' | 'done' | 'error'
  phase: string | null
  started_at: string | null
  finished_at: string | null
  error: string | null
  pulse_md: string | null
}

export interface PulseNote {
  date: string
  filename: string
  content: string
}

export interface ThemeData {
  id: string
  label: string
  description: string
  count: number
}

export interface ThemesResponse {
  date: string
  themes: ThemeData[]
}

export interface ReviewStats {
  total: number
  scrapedAt: string
  weeksRequested: number
  ratingDistribution: Record<string, number>
  avgRating: number
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => apiFetch<{ status: string }>('/health'),

  runPipeline: (req: RunRequest) =>
    apiFetch<{ message: string; status: string }>('/api/run', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  getStatus: () => apiFetch<PipelineStatus>('/api/status'),

  getLatestPulse: () => apiFetch<PulseNote>('/api/pulse/latest'),

  getLatestThemes: () => apiFetch<ThemesResponse>('/api/themes/latest'),

  getReviewStats: () => apiFetch<ReviewStats>('/api/reviews/stats'),

  getLatestEml: () => apiFetch<{ filename: string; content: string }>('/api/eml/latest'),
}
