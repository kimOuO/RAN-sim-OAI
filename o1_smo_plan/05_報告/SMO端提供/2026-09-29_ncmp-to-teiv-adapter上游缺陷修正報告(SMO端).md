# (SMO 端提供)回報 O-RAN SC:ncmp-to-teiv-adapter 缺陷修正 —— 存檔

來源:SMO 端 Claude session,2026-09-29;由使用者轉貼。內容為 SMO 側對 `smo/teiv` 的本地修正與上游提交建議,**DT 端無需動作**,存檔供日後對照。
重點:
1. adapter 映像未打包 TEIV YANG、路徑寫死 → 改成 `TEIV_YANG_MODELS_DIR` 可設並打包進映像。
2. relationship 名稱缺 module 前綴 → `YangModelService` 回傳 `<module>:<name>`。
3. 基底 `debian:bullseye-slim` 裝不到 JDK17 → 本地改 `eclipse-temurin:17-jre`。
4. `MANAGEDELEMENT_MANAGES_*` id 重複前綴(不影響寫入)。
5. ODUFunction `dUpLMNId` 未轉出(null)。
6. `pLMNId` 應為 list(max-elements 1)→ `List<Plmnid>` + ACCEPT_SINGLE_VALUE_AS_ARRAY。
7. **TEIV 本體**:delete 事件含 ≥2 item 會卡死 partition(需另開 JIRA)。
8. adapter workaround:delete 拆單筆。
提交需 mitlab 的 O-RAN SC 帳號(JIRA + Gerrit),步驟見原文。
與 DT 的關聯:#7 是我方 `gen_teiv_links.py` delete 每條一檔的原因;#5 若上游修好,TEIV 的 ODUFunction 會自帶 PLMN。
