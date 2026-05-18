'use client';

// 共享 e2adapter Status snapshot — 之前 useSystemOverview + E2AdapterCard 各 poll 一次, 重複。
import { E2_ADAPTER_BASE_URL } from '@/config';
import { makePoller } from './_sharedPoller';

export interface AdapterStatus {
  sctp_link: {
    enabled: boolean;
    target_host: string;
    target_port: number;
    connected: boolean;
    last_connect_at_ms: number;
    last_disconnect_at_ms: number;
    last_error: string;
    pdu_sent_count: number;
    pdu_recv_count: number;
  };
  e2_setup: {
    completed: boolean;
    accepted_ran_function_ids: number[];
    rejected_ran_function_ids: number[];
  };
  schemas: { loaded: boolean; file_list: string[]; error: string };
  sim_bridge: { cu_url: string; last_e2_node_id_at_ms: number; last_error: string };
  codec_selftest: {
    e2_setup_request_ok: boolean;
    e2_setup_request_size: number;
    kpm_indication_ok: boolean;
    kpm_indication_size: number;
    subscription_decode_ok: boolean;
    subscription_decoded_metrics: string[];
    last_error: string;
  };
}

async function fetchAdapterStatus(): Promise<AdapterStatus> {
  const r = await fetch(
    `${E2_ADAPTER_BASE_URL}/api/v0.1/E2Adapter/Status/AdapterStatusReader/read`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
  );
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  return j.data;
}

const poller = makePoller<AdapterStatus>(fetchAdapterStatus, 2000);
export const useE2AdapterStatus = poller.use;
