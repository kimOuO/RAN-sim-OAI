'use client';
import { useState } from 'react';
import { importScenarioV1 } from '@/services/api/imports';

export default function ImportsPage() {
  const [text, setText] = useState(''); const [msg, setMsg] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  async function submit() {
    setBusy(true); setMsg(null);
    try { const r = await importScenarioV1(JSON.parse(text)); setMsg(`匯入完成:scene ${r.scene_uuid}`); }
    catch (e) { setMsg(`失敗:${e instanceof Error ? e.message : String(e)}`); } finally { setBusy(false); }
  }
  return (
    <section className="shell page">
      <h1>匯入</h1>
      <h2>劇本 JSON(v1)</h2>
      <textarea rows={14} value={text} onChange={(e) => setText(e.target.value)} placeholder='貼上劇本 JSON(docs/scenarios/*.json 格式)' />
      <div className="actions"><button disabled={busy || !text.trim()} onClick={submit}>匯入到 registry</button></div>
      {msg && <p className="msg">{msg}</p>}
      <h2>GLB 掃描 / OSM</h2><p className="muted">走 building-geometry-ingest(:8303);上傳表單:P3-2</p>
    </section>
  );
}
