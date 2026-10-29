'use client';
import { useState } from 'react';
import type { O1Observation } from '@/types/o1';
import { Panel } from './Panel';
import { o1Accepted, o1Http, o1Time } from './O1PmPanels';

const eventLabel = (kind: string) => ({ pnfRegistration: '網元註冊', heartbeat: '心跳', notifyFileReady: 'PM 檔案就緒', notifyNewAlarm: '告警發生', notifyClearedAlarm: '告警清除', notifyChangedAlarm: '告警變更', notifyMOIDeletion: '網元移除' })[kind] ?? kind;
const alarmLabel = (problem: string | undefined) => problem?.includes('internalConnectionLoss') ? 'DT 管理連線中斷' : problem?.includes('loadDownlinkExceededWarning') ? '下行負載超過門檻' : problem || '—';
const severityClass = (severity: string | undefined) => ['CRITICAL', 'MAJOR'].includes(severity ?? '') ? 'bad' : severity === 'WARNING' || severity === 'MINOR' ? 'warn' : 'ok';

export function O1FmPanels({ data }: { data: O1Observation }) {
  const [showHeartbeat, setShowHeartbeat] = useState(false);
  const [outcome, setOutcome] = useState('');
  const fm = data.fm;
  const oldAlarms = data.cm.elements.flatMap((el) => el.alarms.filter((a) => !['CLEARED', 'NORMAL'].includes(a.perceivedSeverity ?? '')).map((a) => ({ ...a, managed_element: el.managed_element })));
  const alarms = fm.current_verified ? fm.active : oldAlarms;
  const notifications = [...data.notifications].reverse().filter((e) => (showHeartbeat || e.kind !== 'heartbeat') && (!outcome || (outcome === 'accepted' ? o1Accepted(e.http_status) : !o1Accepted(e.http_status))));
  return <>
    <Panel title="FM · 告警狀態與歷史" sub={fm.current_verified ? 'O1 目前告警清單' : '目前狀態未查證'} span={12}>
      {!fm.current_verified && <p className="muted small">{data.cm.source === 'snapshot' ? `Run 已停止或目前無法讀取全部網元；以下只顯示最後觀測狀態（${o1Time(fm.observed_at)}）。` : '尚未取得目前告警清單；沒有歷史告警紀錄不等於網路正常。'}</p>}
      {alarms.length ? <table className="tbl"><thead><tr><th>嚴重度</th><th>管理網元</th><th>告警</th><th>物件</th><th>原因</th></tr></thead><tbody>{alarms.map((a) => <tr key={`${a.managed_element}:${a.alarmId}`}><td className={severityClass(a.perceivedSeverity)}><b>{a.perceivedSeverity}</b></td><td className="mono small">{a.managed_element}</td><td>{alarmLabel(a.specificProblem || a.alarmId)}</td><td className="mono small">{a.objectInstance}</td><td className="mono small">{a.probableCause}</td></tr>)}</tbody></table> : <p className={fm.current_verified ? 'ok' : 'muted'}>{fm.current_verified ? '目前已讀取的 O1 網元沒有活動告警。' : '沒有可顯示的活動告警觀測紀錄。'}</p>}
      <div className="o1-report"><b className="small">告警事件紀錄 · {fm.events.length} 筆</b>{!fm.events.length ? <p className="muted small">保留的傳送紀錄內沒有告警發生或清除事件。</p> : <table className="tbl"><thead><tr><th>時間</th><th>事件</th><th>嚴重度</th><th>管理網元</th><th>告警</th><th>VES 回覆</th></tr></thead><tbody>{[...fm.events].reverse().map((e) => <tr key={`${e.id}:${e.at_ms}`}><td className="mono small">{o1Time(e.at)}</td><td>{eventLabel(e.kind)}</td><td className={severityClass(e.perceivedSeverity)}>{e.perceivedSeverity}</td><td className="mono small">{e.managed_element}</td><td>{alarmLabel(e.specificProblem || e.alarmId)}</td><td>{o1Http(e.http_status)}</td></tr>)}</tbody></table>}</div>
      <p className="muted small">目前涵蓋：DT 管理連線中斷（MAJOR）；cell 下行負載超過 50% 持續 15 秒（WARNING）。UE 無線斷線、換手失敗與 PCI 混淆尚未映射成 O1 告警。</p>
    </Panel>
    <Panel title="O1 通知 · VES 傳送紀錄" sub="DT 傳送證據 · SMO 取檔與入庫尚未查證" span={12}>
      <div className="filters"><label className="small"><input type="checkbox" checked={showHeartbeat} onChange={(e) => setShowHeartbeat(e.target.checked)} /> 顯示心跳</label><select aria-label="VES 回覆篩選" value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="">全部傳送結果</option><option value="accepted">VES 已接受</option><option value="other">失敗或未取得回覆</option></select><span className="muted small">最近保留 {data.notifications.length} 筆</span></div>
      {!notifications.length ? <p className="muted">沒有符合的 O1 通知紀錄。</p> : <div className="o1-scroll"><table className="tbl"><thead><tr><th>時間</th><th>事件</th><th>管理網元</th><th>傳送結果</th><th>相關檔案／告警</th></tr></thead><tbody>{notifications.map((e) => <tr key={`${e.id}:${e.at_ms}`}><td className="mono small">{o1Time(e.at)}</td><td>{eventLabel(e.kind)}</td><td className="mono small">{e.managed_element}</td><td className={o1Accepted(e.http_status) ? 'ok' : 'warn'}>{o1Http(e.http_status)}</td><td className="mono small o1-file">{e.filename || e.alarmId || '—'}</td></tr>)}</tbody></table></div>}
    </Panel>
  </>;
}
