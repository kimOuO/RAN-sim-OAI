import type { ApiResponse } from '@/types';

/** 後端一律 POST(backend_rule §7-2);語意在路徑最後一段。 */
export async function post<T>(url: string, body: unknown = {}, init?: { timeoutMs?: number }): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), init?.timeoutMs ?? 30_000);
  try {
    const res = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body ?? {}), signal: ctrl.signal });
    const raw = (await res.json()) as Record<string, unknown>;
    // DU / RU 舊服務用 {status:"success"} 信封,registry / orchestrator 用 {success:true};兩種都接。
    const ok = typeof raw.success === 'boolean' ? raw.success : raw.status === 'success';
    const json = { ...raw, success: ok } as unknown as ApiResponse<T>;
    if (!json.success) throw new Error(`${json.message}${json.errors ? `: ${JSON.stringify(json.errors)}` : ''}`);
    return json.data;
  } finally {
    clearTimeout(t);
  }
}
