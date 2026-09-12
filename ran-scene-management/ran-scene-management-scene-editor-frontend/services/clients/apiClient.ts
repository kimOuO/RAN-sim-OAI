import type { ApiResponse } from '@/types';

/** 後端一律 POST(backend_rule §7-2);語意在路徑最後一段。 */
export async function post<T>(url: string, body: unknown = {}, init?: { timeoutMs?: number }): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), init?.timeoutMs ?? 30_000);
  try {
    const res = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body ?? {}), signal: ctrl.signal });
    const json = (await res.json()) as ApiResponse<T>;
    if (!json.success) throw new Error(`${json.message}${json.errors ? `: ${JSON.stringify(json.errors)}` : ''}`);
    return json.data;
  } finally {
    clearTimeout(t);
  }
}
