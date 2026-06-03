# OAI PRB 計算邏輯 — 原始碼證據鏈

對應 task #100 跟 PRB% 對齊調查。從 `/home/mitlab/openairinterface5g/` 撈出的原始證據。

---

## 證據 1:OAI KPM `RRU.PrbTotDl` 計算公式

`openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm_subs.c`

```c
  return meas_record;
}

/* 3GPP TS 28.522 - section 5.1.1.2.1
  note: this measurement is calculated as per spec */
static meas_record_lst_t fill_RRU_PrbTotDl(__attribute__((unused))uint32_t gran_period_ms, cudu_ue_info_pair_t ue_info, const size_t ue_idx, e2_node_level_stats_t* node_stats)
{
  meas_record_lst_t meas_record = {0};
  
  meas_record.value = INTEGER_MEAS_VALUE;

  // Get the number of DL PRBs
  meas_record.int_val = (ue_info.ue->mac_stats.dl.total_rbs - last_total_prbs[ue_idx].dl) * 100 / (node_stats[1].mac_stats.dl.total_prb_aggregate - node_stats[0].mac_stats.dl.total_prb_aggregate);   // [%]
  last_total_prbs[ue_idx].dl = ue_info.ue->mac_stats.dl.total_rbs;

  return meas_record;
}

/* 3GPP TS 28.522 - section 5.1.1.2.2
  note: this measurement is calculated as per spec */
static meas_record_lst_t fill_RRU_PrbTotUl(__attribute__((unused))uint32_t gran_period_ms, cudu_ue_info_pair_t ue_info, const size_t ue_idx, e2_node_level_stats_t* node_stats)
{
  meas_record_lst_t meas_record = {0};

  meas_record.value = INTEGER_MEAS_VALUE;

  // Get the number of UL PRBs
  meas_record.int_val = (ue_info.ue->mac_stats.ul.total_rbs - last_total_prbs[ue_idx].ul) * 100 / (node_stats[1].mac_stats.ul.total_prb_aggregate - node_stats[0].mac_stats.ul.total_prb_aggregate);   // [%]
  last_total_prbs[ue_idx].ul = ue_info.ue->mac_stats.ul.total_rbs;

  return meas_record;
```

→ 公式:`RRU.PrbTotDl = (UE.total_rbs Δ) × 100 / (node.total_prb_aggregate Δ)`,單位 %。

---

## 證據 2:UE total_rbs 累積點(numerator)

`openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_dlsch.c` (line 1360-1366):

```c
    UE->mac_stats.dl.total_bytes += TBS;
    UE->mac_stats.dl.current_bytes = TBS;
    UE->mac_stats.dl.total_rbs += sched_pdsch->rbSize;
    UE->mac_stats.dl.num_mac_sdu += sdus;
    UE->mac_stats.dl.current_rbs = sched_pdsch->rbSize;
    UE->mac_stats.dl.total_sdu_bytes += dlsch_total_bytes;
    nr_mac->mac_stats.dl.used_prb_aggregate += sched_pdsch->rbSize;
```

→ 每次「真的分到 PDSCH」累積 `sched_pdsch->rbSize`。**只算 user PDSCH,跟 DT 一致**。

---

## 證據 3:Node total_prb_aggregate 累積點(denominator)

`openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_dlsch.c` (line 1399-1424):

```c
void nr_schedule_ue_spec(module_id_t module_id,
                         frame_t frame,
                         slot_t slot,
                         nfapi_nr_dl_tti_request_t *DL_req,
                         nfapi_nr_tx_data_request_t *TX_req)
{
  gNB_MAC_INST *gNB_mac = RC.nrmac[module_id];
  int CC_id = 0;

  /* already mutex protected: held in gNB_dlsch_ulsch_scheduler() */
  AssertFatal(pthread_mutex_trylock(&gNB_mac->sched_lock) == EBUSY,
              "this function should be called with the scheduler mutex locked\n");

  if (!is_dl_slot(slot, &gNB_mac->frame_structure))
    return;

  NR_ServingCellConfigCommon_t *scc = gNB_mac->common_channels[CC_id].ServingCellConfigCommon;
  int bw = scc->downlinkConfigCommon->frequencyInfoDL->scs_SpecificCarrierList.list.array[0]->carrierBandwidth;
  gNB_mac->mac_stats.dl.total_prb_aggregate += bw;

  nfapi_nr_dl_tti_request_body_t *dl_req = &DL_req->dl_tti_request_body;
  post_process_pdsch_t pdsch = { frame, slot, dl_req, TX_req };

  /* PREPROCESSOR */
  gNB_mac->pre_processor_dl(gNB_mac, &pdsch);
}
```

→ 每個 DL slot:
- Line 1412:`if (!is_dl_slot(...)) return;` 不是 DL slot 就跳出
- Line 1416-1417:DL slot 把 `bw` (=106 for 40 MHz) 累積到 denominator

也就是 **denominator = 每 DL slot 都加 106**(不論有沒有 UE)。

---

## 證據 4 ⭐ 關鍵 — `min_rbSize = 5` 強制 PRB 下限

`openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_dlsch.c` (line 750-755):

```c
  qsort(UE_sched, numUE, sizeof(UEsched_t), comparator);
  UEsched_t *iterator = UE_sched;

  const int min_rbSize = 5;

  /* Loop UE_sched to find max coeff and allocate transmission */
  while (iterator->UE != NULL) {
```

`min_rbSize = 5` 是 const 不是 config,**hard-coded 在 PF scheduler**。

---

## 證據 5:`min_rbSize` 怎麼被使用(2 個地方)

### 5.1 跳過 schedule(line 780):

```c
    if (beam.idx < 0) {
      // no available beam
      iterator++;
      continue;
    }
    if (remainUEs[beam.idx] == 0 || n_rb_sched[beam.idx] < min_rbSize) {
      reset_beam_status(&mac->beam_info, frame, slot, iterator->UE->UE_beam_index, slots_per_frame, beam.new_beam);
      iterator++;
      continue;
    }

```

→ 如果 `n_rb_sched < min_rbSize`(剩餘可用 PRB < 5),直接跳過這個 UE 不排程。

### 5.2 直接跳過 UE(line 817-829):

```c
    uint16_t max_rbSize = 1;

    while (rbStart + max_rbSize <= rbStop && !(rballoc_mask[rbStart + max_rbSize + bwp_start] & slbitmap))
      max_rbSize++;

    if (max_rbSize < min_rbSize) {
      LOG_D(NR_MAC,
            "(%d.%d) Cannot schedule RNTI %04x, rbStart %d, rbSize %d, rbStop %d\n",
            frame,
            slot,
            rnti,
            rbStart,
            max_rbSize,
            rbStop);
      reset_beam_status(&mac->beam_info, frame, slot, iterator->UE->UE_beam_index, slots_per_frame, beam.new_beam);
      iterator++;
      continue;
    }

```

→ 如果可用連續 PRB 不到 5,直接跳過 UE(continue)。

### 5.3 nr_find_nb_rb 強制下限(line 895-907):

```c
    const int oh = 3 * 4 + (sched_ctrl->ta_apply ? 2 : 0);
    //const int oh = 3 * sched_ctrl->dl_pdus_total + (sched_ctrl->ta_apply ? 2 : 0);
    nr_find_nb_rb(sched_pdsch.Qm,
                  sched_pdsch.R,
                  1, // no transform precoding for DL
                  sched_pdsch.nrOfLayers,
                  tda_info.nrOfSymbols,
                  sched_pdsch.dmrs_parms.N_PRB_DMRS * sched_pdsch.dmrs_parms.N_DMRS_SLOT,
                  sched_ctrl->num_total_bytes + oh,
                  min_rbSize,
                  max_rbSize,
                  &sched_pdsch.tb_size,
                  &sched_pdsch.rbSize);

    post_process_dlsch(mac, pp_pdsch, iterator->UE, &sched_pdsch);

```

→ `nr_find_nb_rb` 算出能裝下 `num_total_bytes` 的 PRB 數,**強制下限 min_rbSize=5**。

也就是說:**UE 即使只需 1 PRB 容量,scheduler 仍會分至少 5 PRB**。

---

## 推導:OAI 的 PRB% 為何 10.67%

對 195 kbps DL / 1 UE / 40 MHz BW (106 PRB) / TDD DDDDDDDSUU (70-72% DL slot):

```
每個 DL slot scheduler 跑:
  UE 有 BO → 強制分 5 PRB(min_rbSize)
  → numerator += 5 per DL slot

denominator += 106 per DL slot

per DL slot PRB% = 5 / 106 = 4.72%
```

但 OAI 報 10.67%,還多了 5.95%。可能來源:

1. **retx**:scheduler 重排 retx PDU 也累積 rbSize,但 retx 的 rbSize 跟新傳 PDU 一樣大(可能 5 PRB)
2. **多個 UE 競爭時 PRB 分配**:本場景 1 UE 不影響
3. **PDU 切分**:大 SDU 切多個 PDU 各加 12 byte overhead(line 895 `oh = 3 * 4`),需要更多 PRB
4. **某些 slot 不夠 5 PRB 全分**(idle UE 也不排,加上 SSB slot 跳過,denominator 算不算還要看)

主因仍是 `min_rbSize = 5` 強制下限。

---

## DT vs OAI 對比

| 點 | DT | OAI |
|---|---|---|
| Numerator | `prb_used += rb_alloc` per tick | `total_rbs += rbSize` per DL slot |
| Denominator | `n_prb_total += 106` per tick | `total_prb_aggregate += 106` per DL slot |
| **最小 PRB 分配** | 無下限 — `prb_needed = ceil(BO/cap)` 可到 1 | **強制 5 PRB(`min_rbSize=5`)** |
| MCS overhead 補償 | `bytes_per_prb` 含 P0.3 TDD ratio | `num_total_bytes + 12 byte oh` |
| Retransmission | 沒模擬真 ARQ retx | 排 retx 也累積 PRB |

→ DT 跟 OAI **測量定義一樣**(都只算 PDSCH user PRB)。
→ 差別在 **scheduler 策略**:OAI 強制 ≥ 5 PRB,DT 按需要分配。

對齊修法:DT pf_scheduler 加 `MIN_PRB = 5` 下限,可把 prb_pct 從 0.6% 拉到 ~4.7%。
