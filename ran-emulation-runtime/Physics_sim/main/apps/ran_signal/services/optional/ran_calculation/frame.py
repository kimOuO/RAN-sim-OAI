"""座標系轉換(2026-09-13 P5-2)。

整個平台(registry、Mitsuba 場景、UE/gNB 位置)是 **Y-up**(x 東、y 高、z 南);Sionna RT 假設 **z-up**
(天線 pattern 的仰角切面、V/H 極化都以它的 z 為「上」)。以前把座標原封丟進去,幾何光追沒差,但天線
pattern 躺在水平面、V 極化沿南向、扇區方位被塞進仰角軸(見 progress_log P5-1 / P5-2)。

這裡在 engine 邊界做一次剛體旋轉 Rx(+90°):ours (x, y, z) → sionna (x, −z, y);逆轉 (x, y, z)_s → (x, z, −y)。
- 位置(tx / rx / 速度)進 Sionna 前轉;path_gain / H 本身沒座標,不用轉回。
- 幾何:載入 Mitsuba XML 時對每個 <shape> 的 to_world 補一個 <rotate x=1 angle=90>(在既有 scale/translate 之後),
  ply/obj 的相對檔名改絕對路徑後寫到暫存 XML。既有場景檔不用重產。
env PHY_FRAME=zup(預設)| yup(舊行為,對照舊 cache 用)。
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from main.utils.env_loader import get_str

FRAME = get_str("PHY_FRAME", "zup").lower()


def is_zup() -> bool:
    return FRAME == "zup"


def to_sionna(p) -> list[float]:
    """ours (x, y, z) → sionna (x, −z, y)。yup 模式原樣回。"""
    x, y, z = (float(v) for v in p[:3])
    return [x, -z, y] if is_zup() else [x, y, z]


def from_sionna(p) -> list[float]:
    x, y, z = (float(v) for v in p[:3])
    return [x, z, -y] if is_zup() else [x, y, z]


def adapt_scene_xml(path: str) -> str:
    """回傳 z-up 版本的 Mitsuba XML 路徑(yup 模式直接回原路徑)。同內容重用暫存檔。"""
    if not is_zup():
        return path
    src = Path(path)
    raw = src.read_bytes()
    key = hashlib.sha1(raw + str(src.resolve()).encode()).hexdigest()[:12]
    out = Path(tempfile.gettempdir()) / f"ransim_zup_{src.stem}_{key}.xml"
    if out.exists():
        return str(out)
    tree = ET.parse(src)
    root = tree.getroot()
    for shape in root.iter("shape"):
        # 相對檔名 → 絕對(暫存檔不在原目錄)
        for s in shape.findall("string"):
            if s.get("name") == "filename":
                v = s.get("value", "")
                if v and not os.path.isabs(v):
                    s.set("value", str((src.parent / v).resolve()))
        tw = None
        for t in shape.findall("transform"):
            if t.get("name") == "to_world":
                tw = t
                break
        if tw is None:
            tw = ET.SubElement(shape, "transform", {"name": "to_world"})
        # Mitsuba <rotate> 只吃 x/y/z/angle,不能帶 id;用「已有 x=1 angle=90 的 rotate」判斷是否已補過
        if not any(r.get("x") == "1" and r.get("angle") == "90" for r in tw.findall("rotate")):
            ET.SubElement(tw, "rotate", {"x": "1", "y": "0", "z": "0", "angle": "90"})
    tree.write(out, encoding="utf-8", xml_declaration=True)
    return str(out)
