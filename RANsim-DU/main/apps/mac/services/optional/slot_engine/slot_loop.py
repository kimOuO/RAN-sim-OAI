"""Slot-level RLC/MAC delay 模擬器(Phase 0,shadow 模式用,純 Python)。

對齊 OAI RlcSduDelayDl 的精確定義(openair5g nr_rlc_entity_am.c:1761-1762, 1864):
  SDU.time_of_arrival = now              # SDU 進 RLC 時
  waited_time = now - time_of_arrival    # SDU 被切成 PDU「傳給 MAC」那一刻
  RlcSduDelayDl = 100ms 窗內 waited_time 的平均   # = HOL sojourn(到達→傳出)
  ★ 不含 HARQ ACK 往返 ★  (但 HARQ retx 佔用 slot → 間接延後其他 SDU 的傳出)

模型(逐 0.5ms DL slot):
  - TDD:只有 DL slot 能傳(band78 ~DDDDDDDSUU)
  - 排程 pipeline:SDU arrival 後 K0 slot 才 eligible(PDCCH→PDSCH offset + 處理)
  - per-slot SINR = mean + fast-fading → MCS → 每 slot TBS
  - HARQ:首傳 BLER 決定成敗;NACK 排 K_RTT slot 後 retx,retx 佔用該 slot 的容量
  - RLC FIFO:從 queue 取 TBS bytes;SDU 最後一個 byte 被傳出時記 sojourn

★ 這是 Phase 0 的物理模型。magnitude(對齊 OAI 14ms)靠校「物理參數」
  (K0、排程 cadence、BLER 曲線、fading std),不是 /30 那種無意義 fudge。

純 Python、無 Django 相依,可獨立跑 / 單測。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from main.apps.mac.services.optional.link_adaptation.mcs_table import _SINR_TO_MCS
from main.apps.mac.services.optional.slot_engine.bler_table import bler


SLOT_MS = 0.5  # band78 μ=1 → 0.5ms/slot

# mcs → spectral efficiency (bps/RE):由 mcs_table 的 (threshold, mcs, bps_re) 建,缺的 MCS 線性插值
_MCS_EFF_PTS = sorted((m, e) for _, m, e in _SINR_TO_MCS)


def _eff_for_mcs(mcs: int) -> float:
    pts = _MCS_EFF_PTS
    if mcs <= pts[0][0]:
        return pts[0][1]
    if mcs >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        m0, e0 = pts[i]
        m1, e1 = pts[i + 1]
        if m0 <= mcs <= m1:
            return e0 + (e1 - e0) * (mcs - m0) / (m1 - m0)
    return pts[-1][1]


def _mcs_at_op_point(sinr_db: float, target_bler: float) -> int:
    """挑「首傳 BLER ≤ target(OAI target_dl_bler,預設 0.1)」裡最高的可行 MCS。

    用 bler() 本身判斷 → 選 MCS 與評估 BLER 同一條曲線、同一個 ~10% 操作點,自洽。
    這就是 OAI link adaptation:把 MCS 停在 ~10% 首傳失敗率以最大化吞吐(非寫死重傳率)。
    """
    chosen = 0
    for m in range(28):
        if bler(m, sinr_db) <= target_bler:
            chosen = m
    return chosen


@dataclass
class SlotParams:
    slot_ms: float = SLOT_MS
    # TDD pattern:一個 period 內哪些 slot 是 DL(True=DL)。band78 DDDDDDDSUU:
    # 7 DL + 1 special(當半 DL) + 2 UL,period=10 slot。
    tdd_dl_mask: tuple[bool, ...] = (True, True, True, True, True, True, True, True, False, False)
    k0_slots: int = 2          # 排程 pipeline:arrival 後幾 slot 才能被排(PDCCH→PDSCH+處理)
    harq_rtt_slots: int = 4    # HARQ retx 間隔(NACK→retx)
    fading_std_db: float = 2.0 # per-slot fast-fading 標準差
    re_per_prb_slot: int = 144 # 12 subcarrier × 12 symbol
    target_bler: float = 0.1   # link adaptation 目標首傳 BLER(對齊 OAI target_dl_bler)
    sched_period_slots: int = 1  # 改動二 cadence:此 UE 每幾 slot 才有一次排程機會(1=每 DL slot,>1=稀疏)
    discard_timer_ms: float = 0.0  # #2 RLC discardTimer:SDU 等超過此 sim-ms 就丟棄(0=關=無窮,對齊 3GPP discardTimer)
    seed: int | None = None    # 重現用


@dataclass
class _Sdu:
    sid: int
    arrival_abs_slot: int          # 絕對 slot(跨 tick 不歸零),改動一用
    bytes_remaining: int


@dataclass
class SlotEngineState:
    """改動一 — per-UE 跨 tick 持有的引擎狀態,讓 backlog 累積。

    傳同一個 state 連續呼叫 simulate_sdu_delays → 上一 tick 沒排完的 SDU、
    HARQ retx 佔用、slot 時鐘都留著,高負載 phase 排隊才累積得起來。
    不傳 state(=None)時每次用全新狀態 = 舊的 per-tick 孤立行為(會低估 delay)。
    """
    abs_slot: int = 0                                       # 絕對 slot 時鐘
    carry_queue: list = field(default_factory=list)         # 真排隊:已到達且沒排完的 _Sdu(算 backlog,讓 server 連續)
    pending_future: list = field(default_factory=list)      # 還沒到排程機會、根本還沒上車的 _Sdu(下 tick 當新到達重評,不算 backlog)
    harq_busy: dict = field(default_factory=dict)           # abs_slot -> 1(retx 佔用)
    serving: bool = False                                   # load-adaptive cadence:server 是否在服務期(busy 連續排空,跨 tick 持有)


@dataclass
class SlotResult:
    delays_ms: list[float] = field(default_factory=list)   # 每個「傳出」SDU 的 sojourn
    tx_slots: int = 0       # 有傳資料的 slot 數
    retx_slots: int = 0     # 被 retx 佔用的 slot 數
    dropped_sdus: int = 0   # #2 discardTimer:等超時被丟棄的 SDU 數
    dropped_bytes: int = 0  # #2 discardTimer:被丟棄的 byte 數


def _tbs_bytes_per_slot(mcs: int, bps_re: float, n_prb: int, params: SlotParams) -> int:
    """一個 slot、n_prb 個 PRB、此 MCS 能傳幾 byte。"""
    re = n_prb * params.re_per_prb_slot
    bits = re * bps_re
    return int(bits / 8)


def simulate_sdu_delays(
    sdus: list[tuple[float, int]],   # [(arrival_sim_ms, bytes), ...] — arrival 必須是絕對 sim-time
    mean_sinr_db: float,
    n_prb: int,
    sim_dt_ms: float,
    *,
    state: SlotEngineState | None = None,
    params: SlotParams | None = None,
) -> SlotResult:
    """跑一個粗 tick(= sim_dt_ms 的 sim-time = N slot)的 slot 級模擬,回傳 per-SDU sojourn。

    改動一(跨 tick backlog):傳同一個 `state` 連續呼叫,上一 tick 沒排完的 SDU、
    HARQ retx 佔用、slot 時鐘都會留到下一 tick → 高負載 phase 排隊累積,delay 隨之增長。
    不傳 state(=None)時每次用全新狀態 = 舊的 per-tick 孤立行為(低估 delay)。

    ★ sdus 的 arrival_sim_ms 必須是「絕對 sim-time(ms)」(同 arrival_sim_ms 注入時鐘)。
      slot 窗起點用 server-free cursor 決定(見下),不靠外部 process tick → 不會因
      注入-vs-處理 tick 落差灌入虛假等待(舊 now_sim_ms 法會多算 ~1-2 tick)。
    n_prb 是這個 UE 這 tick 分到的 PRB(scheduler 給的)。
    """
    p = params or SlotParams()
    st = state if state is not None else SlotEngineState()
    rng = random.Random(p.seed)
    n_slots = max(1, int(round(sim_dt_ms / p.slot_ms)))
    period = len(p.tdd_dl_mask)
    # slot 窗起點 = M/G/1 server-free cursor(對齊 segment.py 的 _server_free_sim_ms):
    #   - 上 tick 有 backlog(carry_queue 非空)→ server 一直在忙 → 從上次結束 abs_slot 接續
    #   - 上 tick 已排空(server 閒置)→ 跳到本批最早到達,不計虛假閒等(也清掉殘留 retx)
    # 這樣 delay = arrival→傳出 的真實佇列等待,不含「注入 tick 落後處理 tick」那段 pipeline 假象。
    # pending = 本 tick 新到達 + 上 tick「還沒到排程機會」的(pending_future,當新到達重評,非 backlog)
    pending = sorted(
        [_Sdu(sid=i, arrival_abs_slot=int(a_ms / p.slot_ms), bytes_remaining=b)
         for i, (a_ms, b) in enumerate(sdus)] + list(st.pending_future),
        key=lambda s: s.arrival_abs_slot,
    )
    # slot 窗起點 = 正統 M/G/1 server-free cursor:server 從「空閒時刻 st.abs_slot」與
    # 「最早待處理到達」較晚者開始服務。
    #   - 真 backlog:st.abs_slot(上次實際服務結束)通常 ≥ 到達 → 從 abs_slot 連續(真排隊)
    #   - 閒置/輕載:st.abs_slot 落在過去 → start 跳到新到達,不計虛假閒等
    # ★ 關鍵:st.abs_slot 記「實際最後服務 slot+1」(見結尾,非盲目 +整個 tick)→ cursor 貼著
    #   實際工作,不會在輕載震盪時飄離到達 → 修掉 carry artifact(轉換 spike + burst bimodal 220ms)。
    earliest_pending = pending[0].arrival_abs_slot if pending else st.abs_slot
    start = max(st.abs_slot, earliest_pending)
    end = start + n_slots

    queue: list[_Sdu] = list(st.carry_queue)
    pi = 0
    res = SlotResult()
    # 跳過的閒置期 → 清掉落在 start 之前的殘留 retx
    harq_busy_until = {k: v for k, v in st.harq_busy.items() if k >= start}

    P = p.sched_period_slots
    serving = st.serving if st.carry_queue else False  # 閒置起步 → 重新等 occasion(baseline)
    last_active = None  # 最後「實際服務(傳輸或 retx 佔用)」的 slot → server-free cursor 用
    for s in range(start, end):
        # 把到期的 SDU 放進 queue(eligible = arrival + K0,PDSCH pipeline;不再 per-SDU 對齊 occasion)
        while pi < len(pending) and pending[pi].arrival_abs_slot + p.k0_slots <= s:
            queue.append(pending[pi])
            pi += 1

        # #2 RLC discardTimer:佇列是 FIFO(最舊在前),把等超過 discard_timer_ms 的從頭丟掉
        #   → 過載/爛訊號時封頂延遲(對齊真機 RLC discard,而非無窮排隊報 42 秒假延遲)。
        #   門檻設遠高於正常 delay(預設 0=關;啟用時建議 ≥300ms,不影響已對齊的 12-22ms)。
        if p.discard_timer_ms > 0:
            while queue and (s - queue[0].arrival_abs_slot) * p.slot_ms > p.discard_timer_ms:
                d = queue.pop(0)
                res.dropped_sdus += 1
                res.dropped_bytes += d.bytes_remaining

        if not p.tdd_dl_mask[s % period]:
            continue  # 非 DL slot

        # retx 佔用:若這 slot 被先前 NACK 排了 retx,容量先給 retx(簡化:整 slot 佔掉)
        if harq_busy_until.pop(s, 0):
            res.retx_slots += 1
            last_active = s  # server 忙於 retx 也算服務
            continue

        if not queue:
            serving = False  # 排空 → server 休眠,下個 SDU 要重新等 occasion
            continue

        # 改動二 cadence(load-adaptive,gated/exhaustive vacation queue):
        #   - server 從休眠醒來只在「排程機會」slot(s % P == 0)→ 製造 idle/低載 baseline(平均等半 period)
        #   - 一旦 serving 就連續每 DL slot 排空 → 重載=排隊主導,不再每 SDU 疊 occasion 等待(修 burst overshoot)
        if not serving:
            if P > 1 and (s % P) != 0:
                continue  # 還沒到排程機會,server 仍休眠
            serving = True

        # per-slot channel → MCS → TBS
        inst_sinr = mean_sinr_db + rng.gauss(0.0, p.fading_std_db)
        # link adaptation:用 mean SINR(=回報 CQI)把 MCS 停在 ~target BLER 操作點;
        # BLER 改用 inst SINR(實際通道含 fading)評估 → 失敗率自然在 target 附近湧現
        mcs = _mcs_at_op_point(mean_sinr_db, p.target_bler)
        bps_re = _eff_for_mcs(mcs)
        tbs = _tbs_bytes_per_slot(mcs, bps_re, n_prb, p)
        if tbs <= 0:
            continue

        # FIFO drain 這個 slot
        drained = 0
        idx = 0
        while idx < len(queue) and drained < tbs:
            sdu = queue[idx]
            take = min(sdu.bytes_remaining, tbs - drained)
            sdu.bytes_remaining -= take
            drained += take
            if sdu.bytes_remaining == 0:
                # SDU 最後一 byte 被傳出 → 記 sojourn(對齊 OAI waited_time)
                res.delays_ms.append((s - sdu.arrival_abs_slot) * p.slot_ms)
                queue.pop(idx)
            else:
                idx += 1
        if drained > 0:
            res.tx_slots += 1
            last_active = s  # 實際傳輸 → server-free cursor 推進到這
            # 首傳 BLER:這 slot 的 TB 若失敗,排 K_RTT 後 retx(可能落到下一 tick,由 state 帶過去)
            if rng.random() < bler(mcs, inst_sinr):
                harq_busy_until[s + p.harq_rtt_slots] = 1

    # 回寫 state:
    #   carry_queue = 已上車但沒排完的真排隊;pending_future = 還沒上車的(下 tick 重評)
    #   abs_slot = server-free cursor = 實際最後服務 slot+1(非盲目 +整個 tick)→ 修 carry artifact
    st.carry_queue = queue
    st.pending_future = pending[pi:]
    st.abs_slot = (last_active + 1) if last_active is not None else start
    st.serving = serving and bool(queue)  # 仍有 backlog 才維持服務期到下 tick
    st.harq_busy = {k: v for k, v in harq_busy_until.items() if k >= st.abs_slot}
    return res


def avg_delay_ms(res: SlotResult) -> float:
    return sum(res.delays_ms) / len(res.delays_ms) if res.delays_ms else 0.0
