# -*- coding: utf-8 -*-
"""簡報第三版產生器:12 題每頁固定四區塊(場景 / 怎麼做出錯誤 / 指標 / xApp 處置)。

為什麼是產生器而不是手改:前兩版都是逐頁手動調整,改版式就得重來一次,
而且十二頁的用字很難保持一致。內容集中在 Q 字典裡,版式集中在 build_slide,
要改哪一層都不會動到另一層。

用字規範(前兩版被抓到的問題,不再犯):
  - 不用只有專案內部看得懂的代號(q4_v1、NRT、L4、succ_last50 …)
  - 專有名詞第一次出現要就地解釋(A3、PCI、Xn 都在句子裡帶一句白話)
  - 表格的欄位放「短標籤」,敘述放在表格外的區塊
執行:  python scripts/build_ppt_v3.py
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.oxml.ns import qn

SRC = "docs/report/8_27_進度報告_v10十二題.pptx"
DST = "docs/report/8_27_進度報告_v10十二題_v3.pptx"

INK   = RGBColor(0x22, 0x2A, 0x35)   # 主文字
ACCENT= RGBColor(0x1F, 0x38, 0x64)   # 區塊標題
MUTED = RGBColor(0x5B, 0x66, 0x73)   # 次要文字
LINE  = RGBColor(0xD4, 0xDA, 0xE2)
BG_A  = RGBColor(0xF3, 0xF6, 0xFA)   # 場景
BG_B  = RGBColor(0xFA, 0xF7, 0xF1)   # 怎麼做出錯誤
BG_C  = RGBColor(0xF2, 0xF8, 0xF4)   # xApp
OK    = RGBColor(0x1E, 0x6B, 0x3A)   # 驗證通過

# ── 十二題內容 ────────────────────────────────────────────────────────────
# metrics: (短標籤, 這個數字代表什麼, 模擬時怎麼讓它出現)
Q = {
1: dict(name="缺漏鄰區",
 scene="兩座基地台相距 300 公尺,UE 沿直線從一邊走到另一邊。走到中間時對面訊號已經比較強,"
       "照理應該換手過去,但基地台的鄰區表(記錄「我旁邊有哪些鄰居」的清單)裡沒有這一條。",
 sim="直接把來源到目標的那一條鄰居關係從鄰區表刪掉。UE 量得到對面訊號,基地台卻查不到這個鄰居,"
     "沒有對象可以發起換手,只能硬撐到訊號差得斷線,再重新連上對面那一顆。斷線是自然發生的,不是注入的。",
 metrics=[("每分鐘斷線重連次數","UE 撐到掉線後重新連上的頻率,是「該換手卻沒換」最直接的後果","刪掉關係後 UE 自然撐到斷線,模擬器只記錄不介入"),
          ("重連的來源基地台","記錄 UE 是從哪一顆掉過來的,指出缺的是哪一條關係","基地台在處理重新連線時一併記下前一個服務基地台"),
          ("鄰區表查無此關係","排除「有關係但換手失敗」這個完全不同的病因","刪除動作本身就讓這條成立")],
 xapp=["發現:某顆基地台的重連速率高於每分鐘 0.2 次,而且來源集中在同一顆鄰居",
       "確認:查鄰區表,證實這兩顆之間沒有登錄關係(不是換手失敗,是根本不能換)",
       "解決:自動補上這一條鄰居關係",
       "追認:觀察補完之後換手是否真的成功、斷線是否歸零"],
 verify="乾淨重跑 03:24:36 補上關係 → 換手成功 4 次、失敗 0 次 → 斷線歸零"),

2: dict(name="換手縫隙",
 scene="兩顆基地台中間有一小段地帶,雙方訊號幾乎一樣強(實測只差約 0.1 分貝),UE 在這裡持續有換手需求。"
       "同一顆基地台旁邊還有另一條「很少被用到」的鄰居關係,用來測試會不會被誤認成元凶。",
 sim="剪掉這段地帶真正需要的那一條關係,再用訊號計算工具實測、把 UE 停在雙方只差 0.1 分貝的位置,"
     "讓換手需求一直存在卻沒有出口。另外刻意保留一條低使用量的關係當誘餌。",
 metrics=[("每分鐘量測回報次數","UE 多常回報看到這個鄰居,反映需求有多強","把 UE 停在兩邊訊號相當的位置,回報自然持續產生"),
          ("訊號差距","目標與服務基地台的強度差,差距小於 6 分貝就屬於該建關係的範圍","用訊號計算工具逐點實測後決定 UE 位置,不用估算"),
          ("新關係補上後的成功率","補完之後換手是否真的順,門檻 0.95,低於就代表補錯對象","其他關係完全不注入失敗,補上的新關係自然會高於門檻")],
 xapp=["發現:訊號差距在該建關係的範圍內,鄰區表卻查無這一條",
       "排除誘餌:低使用量的那條關係不能因為「數字少」就被當成元凶",
       "解決:補上缺的那一條關係",
       "追認:新關係的換手成功率要達到 0.95 以上"],
 verify="離線與實機兩種方式都補上關係;誘餌關係成功率 0.943 卡在門檻下,未被誤判"),

3: dict(name="深邊緣缺鄰(訊號凹陷區)",
 scene="UE 站在服務基地台天線的訊號凹陷區,腳下訊號只剩 −107.6 dBm、快要斷線;"
       "旁邊另一顆基地台實測強 19.8 分貝,但鄰區表查無這條關係。而且這個角落人很少,量測樣本天生就稀疏。",
 sim="重新排場景幾何,把 UE 放進訊號凹陷區;刪掉通往那顆強鄰居的關係;"
     "並把那顆鄰居標成「禁止駐留」——UE 量得到它、但不准連上去,否則 UE 一斷線就自己跑過去,病就自己好了。"
     "同時保留兩條健康的既有關係當對照組。",
 metrics=[("相對增益","缺的鄰居比服務基地台強多少;這題是 +19.8 分貝,大到不可能是雜訊","改幾何,用訊號計算工具逐點實測到這個差距為止"),
          ("量測樣本的稀疏程度","樣本很少,但規定不准用「樣本不足」當作不處理的理由","邊角只放少量 UE,讓該鄰居的回報量遠低於同場其他鄰居"),
          ("鄰區表剩餘容量","證明加不進去不是因為表滿了,把病因鎖定在偵測","把該基地台的容量使用量一併輸出給 xApp 看")],
 xapp=["發現:服務訊號極弱、旁邊有明顯更強的鄰居,鄰區表卻查無",
       "不得以樣本少駁回:改用「強多少」而不是「看到幾次」來判定",
       "排除容量:先確認鄰區表沒滿,證明阻斷點在偵測而不是空間",
       "解決:補上這一條關係"],
 verify="判準改寫後 07:43:10 重驗通過。落差記錄:題目要求的「每分鐘 0.6 次」絕對稀疏本模擬器做不到"
        "(每個時間刻度每台 UE 都會記錄),改用相對稀疏"),

4: dict(name="未知鄰區",
 scene="場上出現一顆沒有登錄過的基地台。UE 回報得到它的實體編號(PCI,只有 0–1007 個號碼、不同基地台會重複使用),"
       "但這個編號不足以確認它到底是誰,鄰區表裡也查不到。",
 sim="在場景中放進一顆未登錄的基地台,不替它建立任何鄰居關係,讓 UE 自然量測到它。",
 metrics=[("未知編號的回報量","這顆陌生基地台被看到得多頻繁,決定它值不值得處理","放在 UE 會經過的位置,回報量自然累積"),
          ("全域身分抽樣結果","要求 UE 回報對方完整的全域識別碼,把重複的實體編號解成唯一身分","基地台支援這個查詢流程,回傳該編號對應的唯一解"),
          ("兩次抽樣是否一致","同一個對象問兩次要得到同樣答案,才敢寫進鄰區表","場景中該編號只對應一顆基地台,所以兩次結果必然一致")],
 xapp=["發現:UE 一直回報一個鄰區表裡沒有的實體編號",
       "紅線:禁止只憑實體編號就寫入關係——編號會重複,寫錯就把換手送到別人家",
       "解決:先發起全域身分查詢,取得唯一識別碼、且兩次一致,才補上關係"],
 verify="抽樣得到唯一解;離線與實機兩種方式都完成補建"),

5: dict(name="實體編號混淆",
 scene="同一顆服務基地台的周圍,有兩顆不同的基地台用了同一個實體編號。"
       "UE 回報「我看到編號 X」時,基地台無法判斷是哪一顆,換手就有可能送錯地方。",
 sim="讓場景中兩顆不同的基地台共用同一個實體編號,製造出真正的一號兩主。",
 metrics=[("同編號的候選數量","大於 1 就代表混淆成立,這是判定的直接依據","場景中刻意讓兩顆基地台共用同一編號"),
          ("全域身分抽樣結果","把重複的編號解成唯一身分,才知道該送去哪一顆","基地台回傳每個候選各自的完整識別碼"),
          ("群組換手的執行結果","一次把受影響的多台 UE 搬走,只回報成功幾台、不回報是誰","模擬器逐台執行換手後,只把成功計數送回,不揭露 UE 身分")],
 xapp=["發現:同一個實體編號對應到多顆基地台,換手目標無法確定",
       "消歧:用全域身分查詢找出哪一顆才是自己管得到的那顆",
       "解決:對受影響的整群 UE 下一道群組換手指令,一次搬離混淆區",
       "追認:混淆的候選數回到 1"],
 verify="02:09:35 群組換手一次指令搬走 5 台,5 台全數成功,混淆歸零"),

6: dict(name="基地台之間的直接連線不通",
 scene="兩顆基地台之間有一條直接連線(Xn,換手時雙方互相溝通用的專線)。這條線斷了,"
       "但鄰區表上這條關係看起來還是好的。UE 一直想換過去,每一次都在「準備階段」就失敗,沒有一次成功。",
 sim="把關係上「直接連線已建立」這個欄位設成否,並在等待期間每 30 秒把 UE 拉回來源基地台,"
     "確保「有人持續想換手」這個前提不會因為換手被擋住而消失。整段節奏寫在劇本裡由模擬器自己推進,不需要人手動觸發。",
 metrics=[("每分鐘換手嘗試次數","有多少人想換過去;止血成功的話這個數字會掉到 0","UE 被持續拉回來源基地台,需求一直存在"),
          ("換手成功率","這題會是 0,而且是全數失敗,不是偶爾失敗","連線設成不通後,每一次準備都必然失敗"),
          ("失敗原因分佈","全部集中在「準備階段逾時」一種原因,指向傳輸問題而非壅塞","模擬器把真實的失敗原因照實回報,沒有另外偽造")],
 xapp=["發現:某一條關係的換手成功率是 0,而且失敗原因全部集中在準備階段",
       "鑑別:確認這是傳輸不通,不是基地台太忙(太忙的話失敗原因會分散)",
       "止血:暫時封鎖這條關係,讓 UE 不要再白費力氣,同時通報維運端",
       "解除:維運修好連線後,偵測到連線恢復就解除封鎖",
       "追認:成功率要回升到 0.9 以上,才判定真的痊癒"],
 verify="16:17:09 止血,換手嘗試由 6 次/分降到 0;16:55:02 成功率 0.94 判定痊癒"),

7: dict(name="有害鄰居",
 scene="有一條鄰居關係在鄰區表上看起來完全正常,實際上換過去一定失敗(對面的接入程序壞了)。"
       "UE 反覆嘗試、反覆掉話,而其他鄰居關係都是好的。",
 sim="用一個檔案熱開關,對這一條關係注入固定失敗,失敗原因寫成「接入程序問題」。"
     "改用檔案而不是環境變數,是因為環境變數要重啟容器才生效,會打斷 xApp 正在計時的退避流程。"
     "其他關係完全不注入,成功率維持在 0.95 以上當對照組。",
 metrics=[("這條關係的換手成功率","低於 0.6 才算有害;這題是 0","對這一條注入固定失敗"),
          ("每分鐘失敗次數","失敗要持續發生,不能是偶發抖動","UE 被持續拉回來源,嘗試不會停"),
          ("其他關係的成功率","對照組維持 0.95 以上,證明壞的是這一條而不是整顆基地台","注入只針對單一條關係,其餘完全不碰")],
 xapp=["發現:單一條關係成功率崩到 0,同顆基地台的其他關係卻正常",
       "止血:封鎖這條關係,UE 就不會再往這裡撞",
       "試探:過一段時間解封一次,看對面修好了沒",
       "還沒好就再封,而且間隔加倍:300 秒 → 600 秒 → 1200 秒封頂,避免一直干擾",
       "追認:真的修好、成功率回升,才恢復正常使用"],
 verify="劇本七步時間軸無人值守完整跑完 14:40:33 → 14:57:45,含兩輪封鎖與間隔倍增"),

8: dict(name="跨頻缺層",
 scene="同一塊區域疊了兩層網路:3.5 GHz 高頻(容量大、覆蓋小)和 2.1 GHz 低頻(覆蓋大、容量小)。"
       "UE 走到高頻的邊緣時應該落到低頻層繼續服務,但兩層之間一條關係都沒有,UE 只能在邊緣硬撐到斷線。",
 sim="剪掉高頻通往低頻的三條關係。乾擾計算只在同頻之間進行,所以低頻那層對高頻不會造成乾擾,"
     "純粹是「該落下去卻沒有路」。",
 metrics=[("外來頻率上的強訊號數量","同時有兩顆以上不同頻率的強鄰居被看到,代表缺的是一整層不是單一鄰居","把整層的關係一次剪掉三條"),
          ("該來源目前已知的頻率清單","這顆基地台的鄰區表裡有哪些頻率;清單裡沒有低頻就是缺層的證據","剪關係後清單自然只剩同頻"),
          ("邊緣斷線次數","缺層的後果,證明這不只是帳面缺漏而是真的影響服務","UE 走到高頻邊緣沒有出口,自然掉線")],
 xapp=["發現:UE 在邊緣看到成批的外來頻率強訊號,而目前的鄰居清單裡完全沒有這個頻率",
       "判斷:缺的是整個頻率層,不是某一顆鄰居",
       "解決:補上跨頻的鄰居關係,讓 UE 能落到低頻層"],
 verify="離線驗證通過,三條跨頻關係補齊"),

9: dict(name="鄰區表容量已滿",
 scene="一顆熱點基地台的鄰區表已經塞到上限,真正該加的新鄰居加不進去。"
       "表裡有一部分是很久沒被用過的舊關係,佔著空間沒有貢獻。",
 sim="把該基地台的關係灌到容量上限,其中刻意放進幾條長期零活動的舊關係當作可修剪的對象。",
 metrics=[("容量使用量與上限","用了幾條、上限幾條;滿了就會出現新增被拒","把關係灌到上限值"),
          ("新增被拒事件","證明阻斷點在容量,而不是 xApp 沒偵測到——這兩者的處置完全不同","容量滿時基地台回傳明確的拒絕事件,而不是靜默失敗"),
          ("候選的冷度","一條關係多久沒有被用過;越冷越適合被修剪掉","那幾條舊關係從場景開始就沒有任何換手與量測")],
 xapp=["發現:想補新關係卻被拒絕",
       "鑑別:先確認是容量滿了,不是自己沒偵測到——弄錯方向會一直重試補建",
       "解決:找出長期零活動的舊關係修剪掉,騰出空間",
       "再補:空間釋出後重新補上真正需要的新關係"],
 verify="離線驗證通過,取得容量欄位與新增被拒事件的真實格式"),

10: dict(name="過期編號重指",
 scene="鄰區表上有一條關係,指向的實體編號已經過期——對面那顆基地台換了編號。"
       "換手一直被送往一個不存在的目標,每次都失敗。",
 sim="把目標基地台的實體編號改掉,鄰區表上那條關係則保留舊的編號值,製造出「表上的地址是舊的」狀態。",
 metrics=[("這條關係的失敗率","送不到就會失敗,而且是穩定失敗不是偶發","目標編號改掉後,舊地址永遠找不到人"),
          ("抽樣解出的實際編號","跟鄰區表上記的不一樣,這個落差就是判定依據","基地台照實回報目標現在的編號"),
          ("重指後的失敗率","修好之後要歸零,證明改對了地方","改成新編號後換手自然成功")],
 xapp=["發現:某條關係持續失敗,查詢後發現對方現在的編號跟表上記的不同",
       "解決:同一秒內先刪掉舊關係、再加上新關係(原子重指),中間不留空窗",
       "追認:失敗率歸零"],
 verify="03:14:56 完成重指,編號 205 → 233,失敗歸零"),

11: dict(name="殭屍關係",
 scene="鄰區表裡留著一些早就沒在用的關係——對面拆站、或使用者行為改變,已經沒有人會往那裡換手。"
       "它們佔著容量、也干擾判斷,但不是每一條都能刪:有些是刻意保留的。",
 sim="造出四種型態同場並存:完全沒活動的、只有一半沒活動的、被標記為受保護的、以及目標根本不存在的幽靈關係,"
     "看 xApp 會不會一視同仁全刪。",
 metrics=[("每分鐘換手嘗試次數","為 0 代表沒有人想往那裡換","那些關係的目標放在 UE 走不到的地方"),
          ("每分鐘量測回報次數","為 0 代表連看都看不到;要兩個都是 0 才算真殭屍","目標訊號在 UE 位置上量不到"),
          ("持續多久都是 0","短時間為 0 可能只是剛好沒人,要連續滿一整個觀察窗才算數","場景持續運行,讓零活動狀態一路延續"),
          ("受保護標記","被標記的關係即使零活動也不准刪,測 xApp 會不會硬刪","在其中一條關係上設定保護旗標")],
 xapp=["發現:某些關係長期換手嘗試與量測回報同時為 0",
       "分辨:只有「兩者都是 0 且持續滿窗」才刪;只有一項為 0 的不能動",
       "解決:刪除確認無用的關係,把容量還回來",
       "遵守保護:受保護的關係要拒絕刪除、留下紀錄,而且不重試"],
 verify="02:27:16 完成刪除;受保護的關係正確拒刪且未重試;只有一半零活動的關係未被誤刪"),

12: dict(name="封鎖稽核",
 scene="鄰區表裡有些關係被封鎖了。有的封鎖有憑有據(那條路真的一直失敗),"
       "有的則是沒有任何失敗紀錄就被封住——後者等於白白少了一條可用的路,應該解開。",
 sim="做兩條對照:一條被封鎖但歷史上完全沒有失敗紀錄(無據),一條被封鎖且累積 40 次失敗(正當)。"
     "並且把失敗紀錄的時間往前補,確保關係的建立時間早於失敗史——否則累計數會從零開始算,看起來像無據。",
 metrics=[("自建立以來的累積失敗次數","封鎖的憑據;為 0 就代表當初封鎖沒有根據","一條完全不注入失敗,另一條注入並回填歷史時間"),
          ("封鎖旗標與封鎖來源","誰封的、什麼時候封的,決定該不該由 xApp 解開","封鎖動作留下完整的事件紀錄"),
          ("解封後的成功率","解開之後這條路真的能用,才證明當初的封鎖確實是多餘的","無據那條本來就沒問題,解開後換手自然成功")],
 xapp=["發現:某條關係被封鎖,但累積失敗次數是 0",
       "判斷:沒有失敗史卻被封鎖,屬於無據封鎖",
       "解決:解除封鎖,把這條路還回來",
       "追認:解封後觀察換手是否真的成功,而不是解完就算完"],
 verify="11:21:36 五項訊號齊全,無據封鎖解除並完成行為確認;有據的那條正確地不動"),
}


def _lines(text, width_in, pt):
    """估算一段中文在給定寬度下會佔幾行。

    中文字寬約等於字級,英數約半形;用 0.9 當混排係數。這只是估算,
    目的是「不要溢出」而不是精算 —— 寧可高估一點留白。
    """
    cw = pt / 72.0 * 0.92
    per = max(6, int(width_in / cw))
    n = 0
    for seg in (text if isinstance(text, list) else [text]):
        n += max(1, -(-len(seg) // per))
    return n


def _fit(tf, body, width_in, avail_in, start_pt=8.0, min_pt=6.5):
    """字級由大往小試,直到估算高度塞得進方塊為止。"""
    pt = start_pt
    while pt > min_pt:
        h = _lines(body, width_in, pt) * (pt / 72.0 * 1.32)
        if h <= avail_in:
            break
        pt -= 0.5
    return pt


def _clear(slide, keep_top=1.5):
    """清掉內容區塊,保留標題列、副標與頁碼。"""
    for sh in list(slide.shapes):
        top = Emu(sh.top).inches
        left = Emu(sh.left).inches
        if top < keep_top or left > 9.0:
            continue
        sh._element.getparent().remove(sh._element)


def _box(slide, x, y, w, h, fill, label, body, body_size=8.5, label_size=9):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = fill
    box.line.color.rgb = LINE; box.line.width = Pt(0.75)
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = Inches(0.10)
    tf.margin_top = Inches(0.05); tf.margin_bottom = Inches(0.04)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = label
    r.font.size = Pt(label_size); r.font.bold = True; r.font.color.rgb = ACCENT
    p.space_after = Pt(2)
    body_size = _fit(tf, body, w - 0.22, h - 0.30, start_pt=body_size)
    for line in (body if isinstance(body, list) else [body]):
        q = tf.add_paragraph()
        rr = q.add_run(); rr.text = line
        rr.font.size = Pt(body_size); rr.font.color.rgb = INK
        q.space_after = Pt(1.5)
        q.line_spacing = 0.94
    return box


def build_slide(slide, no, d):
    _clear(slide)
    # 副標:題號與病名
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        t = Emu(sh.top).inches
        # 副標的位置在各頁略有出入,改用「內容包含舊標題」來認,位置只當輔助
        if not (0.95 < t < 1.50 and Emu(sh.width).inches > 5.0):
            continue
        if True:
            sh.text_frame.text = f"第 {no} 題 · {d['name']}"
            pr = sh.text_frame.paragraphs[0]
            pr.runs[0].font.size = Pt(13); pr.runs[0].font.bold = True
            pr.runs[0].font.color.rgb = ACCENT
            pPr = pr._p.get_or_add_pPr()
            for tag in ("a:buChar", "a:buAutoNum"):
                for el in pPr.findall(qn(tag)):
                    pPr.remove(el)
            pPr.append(pPr.makeelement(qn("a:buNone"), {}))

    # ① 場景
    _box(slide, 0.35, 1.54, 9.30, 0.70, BG_A, "① 場景　", d["scene"], body_size=8.5)
    # ② 模擬怎麼做出這個錯誤
    _box(slide, 0.35, 2.30, 4.55, 1.28, BG_B, "② 模擬端怎麼做出這個錯誤", d["sim"], body_size=8)
    # ④ xApp 處置
    _box(slide, 5.10, 2.30, 4.55, 1.28, BG_C,
         "④ xApp 做了什麼(發現 → 解決)",
         [f"{i}. {t}" for i, t in enumerate(d["xapp"], 1)], body_size=8)

    # ③ 指標表
    rows = len(d["metrics"]) + 1
    COLW = (2.05, 3.55, 3.70)
    row_h = []
    for m in d["metrics"]:
        ln = max(_lines(m[i], COLW[i] - 0.14, 7.5) for i in range(3))
        row_h.append(max(0.215, ln * 0.125 + 0.06))
    tbl_h = 0.26 + sum(row_h)
    gt = slide.shapes.add_textbox(Inches(0.35), Inches(3.61), Inches(4.0), Inches(0.22))
    rp = gt.text_frame.paragraphs[0].add_run()
    rp.text = "③ 這一題用哪些指標判斷"
    rp.font.size = Pt(9); rp.font.bold = True; rp.font.color.rgb = ACCENT
    gt.text_frame.margin_left = Inches(0.02); gt.text_frame.margin_top = 0

    shp = slide.shapes.add_table(rows, 3, Inches(0.35), Inches(3.82),
                                 Inches(9.30), Inches(tbl_h))
    tbl = shp.table
    for ci, wv in enumerate(COLW):
        tbl.columns[ci].width = Inches(wv)
    tbl.rows[0].height = Inches(0.26)
    for ri, hv in enumerate(row_h, 1):
        tbl.rows[ri].height = Inches(hv)
    heads = ["指標", "這個數字代表什麼", "模擬端怎麼讓它出現"]
    for c, h in enumerate(heads):
        cell = tbl.cell(0, c)
        cell.text = h
        cell.fill.solid(); cell.fill.fore_color.rgb = ACCENT
        pp = cell.text_frame.paragraphs[0]
        pp.runs[0].font.size = Pt(8.5); pp.runs[0].font.bold = True
        pp.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = cell.margin_right = Inches(0.06)
        cell.margin_top = cell.margin_bottom = Inches(0.01)
    for r, (a, b, c) in enumerate(d["metrics"], 1):
        for ci, txt in enumerate((a, b, c)):
            cell = tbl.cell(r, ci)
            cell.text = txt
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if r % 2 else RGBColor(0xF7, 0xF9, 0xFC)
            pp = cell.text_frame.paragraphs[0]
            pp.runs[0].font.size = Pt(7.5)
            pp.runs[0].font.bold = (ci == 0)
            pp.runs[0].font.color.rgb = INK if ci == 0 else MUTED
            pp.line_spacing = 0.92
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Inches(0.06)
            cell.margin_top = cell.margin_bottom = Inches(0.01)

    # 驗證條
    vy = 3.82 + tbl_h + 0.07
    vtxt = "驗證結果:已通過　" + d["verify"]
    vh = max(0.30, _lines(vtxt, 7.68, 8.0) * 0.135 + 0.10)
    if vy + vh > 5.56:                      # 版面底線,寧可縮字不要溢出
        vh = 5.56 - vy
    v = slide.shapes.add_textbox(Inches(0.35), Inches(vy), Inches(7.90), Inches(vh))
    v.fill.solid(); v.fill.fore_color.rgb = RGBColor(0xEC, 0xF5, 0xEE)
    v.line.color.rgb = RGBColor(0xC3, 0xDF, 0xCC); v.line.width = Pt(0.75)
    tf = v.text_frame; tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = Inches(0.10); tf.margin_top = Inches(0.025)
    tf.margin_bottom = Inches(0.02)
    vpt = _fit(tf, vtxt, 7.68, vh - 0.06, start_pt=8.0, min_pt=7.0)
    p = tf.paragraphs[0]
    r1 = p.add_run(); r1.text = "驗證結果:已通過　"
    r1.font.size = Pt(vpt); r1.font.bold = True; r1.font.color.rgb = OK
    r2 = p.add_run(); r2.text = d["verify"]
    r2.font.size = Pt(vpt); r2.font.color.rgb = INK
    p.line_spacing = 0.95


def main():
    prs = Presentation(SRC)
    for i, no in enumerate(range(1, 13)):
        build_slide(prs.slides[3 + i], no, Q[no])
    prs.save(DST)
    print(f"已產生 {DST}({len(prs.slides)} 頁,第 4~15 頁為十二題)")


if __name__ == "__main__":
    main()
