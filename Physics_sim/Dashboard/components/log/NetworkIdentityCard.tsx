'use client';

// 2026-05-16 P4.1 — Network Identity Card。
// 顯示 PLMN、gNB_ID、TAC、SST、RIC IP — 對齊 OAI 設定的關鍵欄位,
// 之前都藏在後端 env / NGAP PDU 內,前端看不到。

import { useE2NodeId } from '@/hooks/feature/log/useE2NodeId';
import { useE2AdapterStatus } from '@/hooks/feature/log/useE2AdapterStatus';

const C_BG = '#1f2937';
const C_BORDER = '#374151';
const C_LABEL = '#9ca3af';
const C_VAL = '#e5e7eb';
const C_OK = '#10b981';
const C_WAIT = '#f59e0b';

function Row({ label, value, status }: { label: string; value: React.ReactNode; status?: 'ok' | 'wait' }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, padding: '2px 0' }}>
      <span style={{ color: C_LABEL }}>{label}</span>
      <span style={{ color: status === 'ok' ? C_OK : status === 'wait' ? C_WAIT : C_VAL, fontFamily: 'monospace' }}>
        {value}
      </span>
    </div>
  );
}

export function NetworkIdentityCard() {
  const { data: nodeId, error: nodeErr } = useE2NodeId();
  const { data: adapter } = useE2AdapterStatus();

  if (!nodeId) {
    return (
      <div style={{
        background: C_BG, border: `1px solid ${C_BORDER}`, borderRadius: 8,
        padding: 16, color: C_LABEL, fontSize: 13,
      }}>
        Network Identity: {nodeErr ? `unreachable (${nodeErr})` : 'loading...'}
      </div>
    );
  }

  const plmn = nodeId.global_e2_node_id.plmn_id;
  const gnb = nodeId.global_e2_node_id.gnb_id;
  // TAC / SST 從第一個 cell 取(per-cell 預期都一樣,異質再開 cell-level 顯示)
  const firstCell = nodeId.components?.[0]?.cells?.[0];
  const tac = firstCell?.tac;
  const sst = firstCell?.s_nssai?.sst;
  const servedPlmn = firstCell?.served_plmn;

  const ric = adapter?.sctp_link;

  return (
    <div style={{
      background: C_BG, border: `1px solid ${C_BORDER}`, borderRadius: 8,
      padding: 14, fontSize: 12,
    }}>
      <div style={{
        fontSize: 13, fontWeight: 600, color: '#cbd5e1', marginBottom: 10,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span>Network Identity</span>
        <span style={{ fontSize: 11, color: C_LABEL }}>對齊 OAI 設定</span>
      </div>

      <Row
        label="PLMN (MCC / MNC)"
        value={`${plmn.mcc} / ${plmn.mnc}  (BCD ${plmn.mnc_digit_count}-digit)`}
      />
      <Row
        label="Served PLMN"
        value={servedPlmn || '—'}
        status={servedPlmn === `${plmn.mcc}${plmn.mnc.replace(/^0+/, '')}` ? 'ok' : undefined}
      />
      <Row
        label="gNB ID"
        value={`${gnb.value_hex}  (${gnb.bit_length}-bit, int ${gnb.value_int})`}
      />
      <Row
        label="TAC"
        value={tac !== undefined ? `0x${tac.toString(16)}  (${tac})` : '—'}
      />
      <Row
        label="S-NSSAI SST"
        value={sst !== undefined ? `${sst} ${sstLabel(sst)}` : '—'}
      />

      <div style={{ borderTop: `1px dashed ${C_BORDER}`, margin: '8px 0' }} />

      <Row
        label="RAN Functions"
        value={nodeId.ran_functions.map(f => `#${f.ran_function_id}`).join('  ')}
      />
      <Row
        label="DU components"
        value={nodeId.components?.length || 0}
      />
      <Row
        label="Total cells"
        value={nodeId.components?.reduce((s, c) => s + (c.cells?.length || 0), 0) || 0}
      />

      <div style={{ borderTop: `1px dashed ${C_BORDER}`, margin: '8px 0' }} />

      <Row
        label="RIC E2-Term"
        value={ric ? `${ric.target_host}:${ric.target_port}` : '—'}
        status={ric?.connected ? 'ok' : ric?.enabled ? 'wait' : undefined}
      />
      <Row
        label="SCTP"
        value={ric?.connected ? `connected (${ric.pdu_sent_count}↑ ${ric.pdu_recv_count}↓)` : ric?.last_error || 'disconnected'}
        status={ric?.connected ? 'ok' : 'wait'}
      />
    </div>
  );
}

function sstLabel(sst: number): string {
  switch (sst) {
    case 1: return '(eMBB)';
    case 2: return '(URLLC)';
    case 3: return '(mMTC)';
    case 4: return '(V2X)';
    default: return '';
  }
}
