# E2SM-CCC Cell On/Off — xApp 對接格式(DT E2 node 期望收到的)

> 給 **xApp 開發者** 的對接文件:我們(DT gNB E2 node)透過 **E2SM-CCC(Cell Configuration and Control)** 支援「開關 cell / 節能」。本文說明我們在 E2 Setup 廣播什麼、xApp 要送什麼格式的 RIC Control、以及我們如何回報。
>
> 依據:O-RAN.WG3.E2SM-CCC(R003 v04+,2024-02)、3GPP TS 28.541 R18、srsRAN `oran-sc-ric` CCC 實作(JSON 封裝參考)。
> 信心標註:**[H]** 高(規範/OSC 實作交叉驗證)、**[M]** 中(規範引用+blog,實作前需對 spec PDF 再確認)。

---

## 0. TL;DR
- E2SM-CCC 用 **JSON** 編碼(不是 ASN.1),外層包進 E2AP 的 OCTET STRING。**[H]**
- RAN function:**OID `1.3.6.1.4.1.53148.1.1.2.4`**,預設 **RAN function ID = 4**,OSC RMR type **12040**。**[H]**
- xApp 下 **RIC CONTROL**,Header `ricStyleType=2`,Message 帶「要改哪些 cell 的哪些 Configuration Structure(新值)」。**[H]**(封裝已對 OSC `oran-sc-ric` CCC 實作逐字驗證)
- **關 cell(主路徑,我方預設支援)**:寫 3GPP `NRCellDU.administrativeState = LOCKED`;開回來 `UNLOCKED`。**[H]**
- **關 cell(節能狀態機,選配)**:寫 `O-CESManagementFunction.energySavingControl = toBeEnergySaving`。**[M,待 spec PDF 定版]**
- 我們 RAN 端**負責趕人 + 完成狀態轉換並回報**(xApp 下目標狀態即可,不需自己先下 HO)。
- **我方 decoder 兩種都收**:`ranConfigurationStructureName` 是 `NRCellDU`(admin state)或 `O-CESManagementFunction`(energy saving)都能解成「開/關該 cell」。

> **驗證狀態(2026-07-02)**:JSON 封裝(header/message/cellGlobalId/listOfConfigurationStructures/old-newValuesOfAttributes)+ RAN fn ID 4 + RMR 12040 = **已對 srsRAN `oran-sc-ric` CCC 原始碼逐字確認**。`administrativeState`/`cellState`/`operationalState` 值域 = 3GPP TS 28.541 多來源確認。`energySaving*` / `O-CESManagementFunction` 確切拼字 = 規範引用+blog(**ETSI TS 104 040 PDF 目前需登入、403 擋下,尚未用一手 PDF 定版**)。

---

## 1. 能力發現(E2 Setup / RAN Function Definition)
我們的 E2 node 在 **E2 Setup Request** 用 RAN Function Name IE 廣播 CCC 的 OID(`PrintableString`),RIC 存進 R-NIB;xApp 即可發現本 node 支援 CCC。**[H]**

RAN Function Definition(JSON)宣告我們支援的:
- **cell-level** Configuration Structure:`O-CESManagementFunction`(節能)——屬性 `energySavingState`(讀)、`energySavingControl`(寫)、`cesSwitch`(寫)。**[M]**
- 每個可控 cell 的 `cellGlobalId`(PLMN + NR Cell Identity)。
- 每屬性標 read / write 能力。

> 我們支援的**子集**:目前只開放「cell 節能開關」這組屬性(+ 直接 `administrativeState`);slice(O-RRMPolicyRatio)等其它 CCC 結構暫不支援。

---

## 2. xApp → RIC CONTROL(關/開 cell)

**Control Header(JSON)** **[H]**
```json
{ "controlHeaderFormat": { "ricStyleType": 2 } }
```

**Control Message(JSON)** — 關掉某 cell(進入節能): **[H 封裝 / M 屬性名]**
```json
{
  "controlMessageFormat": {
    "listOfCellsControlled": [
      {
        "cellGlobalId": {
          "plmnIdentity": { "mcc": "001", "mnc": "01" },
          "nRCellIdentity": "0x00000001"
        },
        "listOfConfigurationStructures": [
          {
            "ranConfigurationStructureName": "O-CESManagementFunction",
            "oldValuesOfAttributes": { "energySavingState": "isNotEnergySaving" },
            "newValuesOfAttributes": { "energySavingControl": "toBeEnergySaving" }
          }
        ]
      }
    ]
  }
}
```

**開回來(退出節能)**:`newValuesOfAttributes = { "energySavingControl": "toBeNotEnergySaving" }`。

**替代:直接硬開關(不走節能狀態機)** —— 寫 3GPP `NRCellDU.administrativeState`: **[M]**
```json
"listOfConfigurationStructures": [{
  "ranConfigurationStructureName": "NRCellDU",
  "oldValuesOfAttributes": { "administrativeState": "UNLOCKED" },
  "newValuesOfAttributes": { "administrativeState": "LOCKED" }   // LOCKED = 關
}]
```

> 傳輸細節(參考 OSC `oran-sc-ric`):header/message 為 **UTF-8 JSON bytes**,放進 E2AP RIC-Control-Request 的 OCTET STRING;RMR message type 用 **12040**。**[H]**

---

## 3. 屬性值域(cell 開關相關)
| 屬性 | 結構 | 值 | 說明 |
|---|---|---|---|
| `energySavingControl` | O-CESManagementFunction | `toBeEnergySaving` / `toBeNotEnergySaving` | **xApp 寫**:觸發進入/退出節能 [M] |
| `energySavingState` | O-CESManagementFunction | `isNotEnergySaving` / `isEnergySaving` | **node 回報**:目前節能狀態 [M] |
| `cesSwitch` | O-CESManagementFunction | `TRUE` / `FALSE` | 每 cell 是否啟用 CES [M] |
| `administrativeState` | NRCellDU (28.541) | `LOCKED` / `UNLOCKED`(default LOCKED)| **可寫**:直接開關(OAM 允許使用與否)[H] |
| `cellState` | NRCellDU | `IDLE` / `INACTIVE` / `ACTIVE` | 使用狀態 [H] |
| `operationalState` | NRCellDU | `ENABLED` / `DISABLED` | **唯讀** [H] |

---

## 4. 節能狀態機 + 誰趕人(正規流程) **[H]**
```
isNotEnergySaving ──xApp: toBeEnergySaving──► toBeEnergySaving
                                                  │  (TS-xApp 訂 CCC indication,把 UE 換手趕走)
                                                  ▼  UE 清空後
                                             isEnergySaving   ← E2 node 自己轉換 + 回報
                                                  │
                          ◄──xApp: toBeNotEnergySaving──  (退出節能,cell 開回)
```
- **xApp 只下「目標狀態」**;**RAN 端(我們)負責實現**:停止收新 UE、把現有 UE HO 走、清空後轉 `isEnergySaving` 真正關閉 RF,並回報。
- UE offload 在標準多廠商部署是 **TS-xApp** 做(訂 CCC indication 得知 `toBeEnergySaving` → 執行 HO);我們 DT 端也可由 node 自己內部趕人(單機 demo)。
- 決策來源可以是 ES-rApp(Non-RT,經 A1)或直接 ES-xApp 經 CCC;本 node 只認 **CCC control** 這條。

---

## 5. node → RIC INDICATION(狀態回報) **[H 機制 / M 欄位]**
xApp 可 **RIC Subscription** 訂 `O-CESManagementFunction` 屬性變化;我們在 cell 狀態轉換(如 `toBeEnergySaving → isEnergySaving`)時發 **RIC Indication(report)**,內容為變更後的 Configuration Structure(含 `energySavingState` 新值 + `cellGlobalId`)。TS-xApp 據此趕人。

---

## 6. 參考實作現況(重要)
- **srsRAN `oran-sc-ric`**:有 CCC xApp(`simple_ccc_xapp`),但**只做 slice(O-RRMPolicyRatio),沒有 cell on/off** → 我們照它的 **JSON 封裝格式**,但 cell 開關屬性要自訂子集。**[H]**
- **FlexRIC / onos-e2-sm / ORANSlice**:**都沒有** CCC cell on/off。ORANSlice 的 CCC 還用 Protobuf 非標準。**[H]**
- 結論:**業界沒有現成的 CCC cell on/off 開源可抄** → 封裝走 OSC 格式,屬性/狀態機照 O-RAN E2SM-CCC + 28.541 定義,我們是自己實作。

---

## 7. 給 xApp 開發者的一句話
> 向 RIC 查到本 node 的 CCC RAN function(OID `...53148.1.1.2.4`)後,送 **RIC Control**:Header `ricStyleType=2`,Message 指定 `cellGlobalId` + `ranConfigurationStructureName=O-CESManagementFunction`,`newValuesOfAttributes={"energySavingControl":"toBeEnergySaving"}` 即可請求關閉該 cell;RAN 會趕人、關閉、並回報 `energySavingState=isEnergySaving`。開回來送 `toBeNotEnergySaving`。

> ⚠️ 標 **[M]** 的確切結構名(`O-CESManagementFunction`)與屬性名,實作前我方會對 O-RAN.WG3.E2SM-CCC spec PDF 做最終定版,若有出入以規範為準並同步更新本文件 §2/§3。
