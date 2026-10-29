export interface O1Container {
  name: string; role: string; status: string; gnb: string; meid: string; managed_element: string; unit_type: string;
  host: string; netconf_port: string; sftp_port: string; ves_url: string; pm_interval_sec: string; run_id: string;
  started_at: string | null; restart_count: number;
}
export interface O1Alarm {
  managed_element?: string; alarmId: string; objectInstance?: string; perceivedSeverity?: string;
  alarmType?: string; probableCause?: string; specificProblem?: string; alarmRaisedTime?: string; alarmClearedTime?: string;
}
export interface O1Event extends Partial<O1Alarm> {
  id: string; at: string; at_ms: number; kind: string; managed_element: string; http_status: number | null; filename?: string;
}
export interface O1Cell {
  dn: string; kind: string; local_cell_id: string | number | null; nRPCI: string | number | null; nRTAC: string | number | null;
  arfcnDL: string | number | null; bSChannelBwDL: string | number | null; bSChannelBwUL: string | number | null;
  administrativeState: string | null; operationalState: string | null; cellState: string | null;
  numberOfRBs: string | number | null; plmn: string[];
}
export interface O1Element {
  managed_element: string; gnb: string; unit_type: string; source: 'o1' | 'scene'; observed_at: string | null;
  vendor: string | null; software_version: string | null; cells: O1Cell[]; alarms: O1Alarm[];
  jobs: { dn: string; metrics: string[]; granularity_sec: number | null; reporting_sec: number | null }[];
}
export interface O1PmFile {
  filename: string; managed_element: string; source: 'o1_xml' | 'ves_log'; end_time: string | null;
  duration_sec: number | null; suspect: boolean | null; http_status: number | null;
  rows: { object: string; suspect: boolean; metrics: Record<string, number | null> }[];
}
export interface O1DtCell {
  cell_id: string; connected_ues: number; throughput_dl_mbps: number; throughput_ul_mbps: number; prb_pct_dl: number | null;
}
export interface O1Observation {
  scene_run_uuid: string; observed_at: string; smo_receipt_verified: boolean; containers: O1Container[]; warnings: string[];
  scope: { run_id: string; started_at: string | null; stopped_at: string | null; scenario_id: string;
    mes: { gnb: string; cucp: string; du: string; dus?: { me: string }[] }[] };
  pm: { trend_source: string; trend: { at_sim_ms: number; wall_time_ms: number; cells: O1DtCell[] }[]; files: O1PmFile[] };
  cm: { source: 'o1' | 'snapshot' | 'scene'; observed_at: string | null; elements: O1Element[] };
  fm: { current_verified: boolean; observed_at: string | null; active: O1Alarm[]; events: O1Event[] };
  notifications: O1Event[];
}
