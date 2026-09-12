"""GLB(glTF binary)讀取器,純 numpy。

自 Omniverse backend `glb_to_usd.py` 抽出 parse_glb / read_accessor / iter_mesh_instances / estimate_floor_y
(2026-09-12 P1-4);`convert_glb_to_usd()` 本身留在 Omniverse。
"""
from __future__ import annotations

import base64
import json
import os
import struct
from pathlib import Path
from typing import Any

import numpy as np

# glTF componentType → numpy dtype
_COMPONENT_DTYPE = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}
_TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

_MIME_EXT = {"image/jpeg": ".jpg", "image/png": ".png"}

GLB_MAGIC = 0x46546C67  # 'glTF'
_CHUNK_JSON = 0x4E4F534A
_CHUNK_BIN = 0x004E4942


class GlbError(ValueError):
    """GLB 內容不合法或用到不支援的功能。"""


# ────────────────────────── 解析 ──────────────────────────

def parse_glb(blob: bytes) -> tuple[dict[str, Any], bytes]:
    """拆出 (glTF JSON, binary chunk)。長度欄位不一致就直接擋下 —— 半截的
    上傳檔若放行，會在後面 accessor 取值時變成難懂的 index error。"""
    if len(blob) < 12:
        raise GlbError("檔案太小，不是有效的 GLB")
    magic, version, length = struct.unpack("<III", blob[:12])
    if magic != GLB_MAGIC:
        raise GlbError("不是 GLB 檔（magic 不符，若為 .gltf 純文字格式請先轉成 .glb）")
    if version != 2:
        raise GlbError(f"只支援 glTF 2.0，收到 version={version}")
    if length != len(blob):
        raise GlbError(f"檔案不完整：header 宣告 {length} bytes，實際 {len(blob)} bytes")

    gltf: dict[str, Any] | None = None
    binary = b""
    off = 12
    while off + 8 <= len(blob):
        clen, ctype = struct.unpack("<II", blob[off:off + 8])
        data = blob[off + 8:off + 8 + clen]
        if len(data) < clen:
            raise GlbError("檔案不完整：chunk 長度超出檔案結尾")
        if ctype == _CHUNK_JSON:
            gltf = json.loads(data)
        elif ctype == _CHUNK_BIN:
            binary = data
        off += 8 + clen + (-clen % 4)

    if gltf is None:
        raise GlbError("GLB 缺少 JSON chunk")

    required = gltf.get("extensionsRequired") or []
    if required:
        raise GlbError(
            "不支援的 glTF 擴充：" + ", ".join(required)
            + "（例如 Draco 壓縮 / KTX2 貼圖，請先用 gltf-transform 解壓後再匯入）"
        )
    return gltf, binary


def _buffer_bytes(gltf: dict, binary: bytes, idx: int) -> bytes:
    """取第 idx 個 buffer 的位元組。GLB 的 buffer 0 無 uri（= binary chunk）；
    其餘只支援 data: URI，外部檔案沒有一起上傳所以拿不到。"""
    buf = gltf["buffers"][idx]
    uri = buf.get("uri")
    if uri is None:
        return binary
    if uri.startswith("data:"):
        return base64.b64decode(uri.split(",", 1)[1])
    raise GlbError(f"不支援外部 buffer 檔案：{uri}")


def _view_bytes(gltf: dict, binary: bytes, view_idx: int) -> tuple[bytes, int]:
    """回傳 (該 bufferView 的位元組, byteStride)。"""
    bv = gltf["bufferViews"][view_idx]
    raw = _buffer_bytes(gltf, binary, bv.get("buffer", 0))
    off = bv.get("byteOffset", 0)
    return raw[off:off + bv["byteLength"]], bv.get("byteStride", 0)


def read_accessor(gltf: dict, binary: bytes, idx: int) -> np.ndarray:
    """讀 accessor → shape (count, n) 的 numpy 陣列，已處理 byteStride 交錯排列。"""
    acc = gltf["accessors"][idx]
    n = _TYPE_COUNT[acc["type"]]
    dtype = np.dtype(_COMPONENT_DTYPE[acc["componentType"]])
    count = acc["count"]

    if "bufferView" not in acc:  # 稀疏/全零 accessor
        return np.zeros((count, n), dtype=dtype)

    data, stride = _view_bytes(gltf, binary, acc["bufferView"])
    start = acc.get("byteOffset", 0)
    elem = dtype.itemsize * n

    if stride and stride != elem:
        # 交錯排列：逐元素跨 stride 取，不能一口氣 frombuffer
        out = np.empty((count, n), dtype=dtype)
        for i in range(count):
            o = start + i * stride
            out[i] = np.frombuffer(data, dtype=dtype, count=n, offset=o)
        return out
    return np.frombuffer(data, dtype=dtype, count=count * n, offset=start).reshape(count, n)


def _normalize_uv(uv: np.ndarray) -> np.ndarray:
    """UV 若以整數型別儲存則依 glTF 規範還原到 0..1。"""
    if uv.dtype == np.uint8:
        return uv.astype(np.float32) / 255.0
    if uv.dtype == np.uint16:
        return uv.astype(np.float32) / 65535.0
    return uv.astype(np.float32)


# ────────────────────────── node 階層 ──────────────────────────

def _node_matrix(node: dict) -> np.ndarray:
    """單一 node 的區域變換矩陣（4x4，row-vector 慣例：p' = p @ M）。"""
    if "matrix" in node:
        # glTF 的 matrix 是 column-major，轉置後即可用 row-vector 相乘
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4, order="F").T

    m = np.eye(4)
    if "scale" in node:
        m = np.diag([*node["scale"], 1.0]) @ m
    if "rotation" in node:
        x, y, z, w = node["rotation"]
        r = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w), 0],
            [2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w), 0],
            [2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y), 0],
            [0, 0, 0, 1],
        ], dtype=np.float64)
        m = m @ r
    if "translation" in node:
        t = np.eye(4)
        t[3, :3] = node["translation"]
        m = m @ t
    return m


def iter_mesh_instances(gltf: dict):
    """走訪 scene 的 node 樹，yield (mesh_index, 世界變換矩陣)。

    掃描類 GLB 常見的做法是「一個 root 掛 N 個沒有 transform 的子 node」，
    但手工場景會有巢狀 transform，所以照規範完整累乘。"""
    nodes = gltf.get("nodes", [])
    scenes = gltf.get("scenes", [])
    scene_idx = gltf.get("scene", 0)
    roots = scenes[scene_idx].get("nodes", []) if scenes else list(range(len(nodes)))

    stack = [(i, np.eye(4)) for i in reversed(roots)]
    seen: set[int] = set()
    while stack:
        idx, parent = stack.pop()
        if idx in seen:  # 防禦性：規範上 node 樹不該有環
            continue
        seen.add(idx)
        node = nodes[idx]
        world = _node_matrix(node) @ parent
        if "mesh" in node:
            yield node["mesh"], world
        for child in reversed(node.get("children", [])):
            stack.append((child, world))


# ────────────────────────── 貼圖 ──────────────────────────

def _extract_images(gltf: dict, binary: bytes, tex_dir: Path) -> list[str | None]:
    """把內嵌貼圖寫成 tex_dir 底下的獨立檔，回傳每個 image 的檔名（失敗為 None）。"""
    images = gltf.get("images", [])
    if not images:
        return []
    tex_dir.mkdir(parents=True, exist_ok=True)
    out: list[str | None] = []
    for i, img in enumerate(images):
        ext = _MIME_EXT.get(img.get("mimeType", ""), ".bin")
        try:
            if "bufferView" in img:
                data, _ = _view_bytes(gltf, binary, img["bufferView"])
            elif str(img.get("uri", "")).startswith("data:"):
                head, b64 = img["uri"].split(",", 1)
                data = base64.b64decode(b64)
                if "png" in head:
                    ext = ".png"
                elif "jpeg" in head or "jpg" in head:
                    ext = ".jpg"
            else:
                out.append(None)  # 外部貼圖檔沒隨 GLB 上傳，只能跳過
                continue
        except Exception:  # noqa: BLE001
            out.append(None)
            continue
        fname = f"tex_{i:03d}{ext}"
        (tex_dir / fname).write_bytes(data)
        out.append(fname)
    return out


def _material_image(gltf: dict, mat_idx: int | None) -> tuple[int | None, list[float]]:
    """material → (baseColorTexture 對應的 image index, baseColorFactor RGB)。"""
    fallback = [0.65, 0.65, 0.65]
    if mat_idx is None:
        return None, fallback
    mat = gltf.get("materials", [])[mat_idx]
    pbr = mat.get("pbrMetallicRoughness", {}) or {}
    factor = pbr.get("baseColorFactor")
    rgb = [float(c) for c in factor[:3]] if factor else fallback
    tex_ref = pbr.get("baseColorTexture")
    if not tex_ref:
        return None, rgb
    tex = gltf.get("textures", [])[tex_ref["index"]]
    return tex.get("source"), rgb


def _index_offsets(collected: list[dict[str, Any]]) -> list[int]:
    """各 part 在合併後點陣列中的起始索引。"""
    offsets = []
    total = 0
    for c in collected:
        offsets.append(total)
        total += len(c["points"])
    return offsets


def estimate_floor_y(points: np.ndarray, faces: np.ndarray) -> float:
    """估「真正的地板高度」——不能取模型最低點。

    掃描常會帶到樓梯下方、樓下結構或飄浮雜訊，最低點比可走的地板低一大截
    （這份走廊實測差 2.15 m）。用最低點對齊地面，會讓整條走廊懸空，
    站在 y=0 的 UE 就跑到地板底下。

    改用「朝上的水平面」面積加權高度直方圖峰值：地板是室內面積最大的朝上平面。
    """
    v0, v1, v2 = points[faces[:, 0]], points[faces[:, 1]], points[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    area = np.linalg.norm(n, axis=1) / 2.0
    unit = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    up = (np.degrees(np.arcsin(np.clip(np.abs(unit[:, 1]), 0, 1))) > 60.0) & (unit[:, 1] > 0)
    if not up.any():
        return float(points[:, 1].min())
    cy = (v0[:, 1] + v1[:, 1] + v2[:, 1]) / 3.0
    ys, ws = cy[up], area[up]
    bins = np.arange(ys.min(), ys.max() + 0.1, 0.1)
    if len(bins) < 2:
        return float(ys.min())
    hist, edges = np.histogram(ys, bins=bins, weights=ws)
    i = int(hist.argmax())
    return float((edges[i] + edges[i + 1]) / 2.0)


# ────────────────────────── 主流程 ──────────────────────────
