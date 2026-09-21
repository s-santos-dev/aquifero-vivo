const apiUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
const pageSize = 100
export type Page<T> = { items: T[]; total: number; page: number; page_size: number; pages: number }

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, { signal })
  if (!response.ok) throw new Error(response.status >= 500 ? 'A API encontrou um problema ao consultar os dados.' : 'Não foi possível carregar os dados solicitados.')
  return response.json() as Promise<T>
}

export async function getAllPages<T>(path: string, signal?: AbortSignal): Promise<T[]> {
  const separator = path.includes('?') ? '&' : '?'
  const first = await getJson<Page<T>>(`${path}${separator}page=1&page_size=${pageSize}`, signal)
  if (first.pages <= 1) return first.items
  const remaining = await Promise.all(Array.from({ length: first.pages - 1 }, (_, index) => getJson<Page<T>>(`${path}${separator}page=${index + 2}&page_size=${pageSize}`, signal)))
  return [first.items, ...remaining.map((page) => page.items)].flat()
}
