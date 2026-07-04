export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail)
    this.name = 'ApiError'
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

let authToken: string | null = null
export function setAuthToken(t: string | null) {
  authToken = t
}

export async function apiRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      if (j && typeof j.detail === 'string') detail = j.detail
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
