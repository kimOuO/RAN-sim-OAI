"""Mitsuba XML scene builder — 把建築 box 列表轉成 Mitsuba 3 XML 給 Sionna RT 吃。

可當 library 被 Django import（`build_from_buildings()` / `write_xml()`），
也可被 tools/scene_to_mitsuba.py CLI 薄殼呼叫。

簡化假設：
- 建築全當 axis-aligned box（忽略 rotation_xyz_deg）
- 地面 → itu_concrete（未來可接 itu_medium_dry_ground）
- Y-up 右手座標（和 scene_config.json 一致）
- Sionna RT 辨識 id 開頭為 `itu_` 的 BSDF 當 radio material
"""
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent


MATERIAL_MAP: dict[str, str] = {
    "concrete": "itu_concrete",
    "glass": "itu_glass",
    "metal": "itu_metal",
    "brick": "itu_brick",
    "wood": "itu_wood",
}

DEFAULT_GROUND_SIZE = (1000.0, 1000.0)
DEFAULT_GROUND_POSITION = (0.0, 0.0, 0.0)


def _material_to_itu(material_name: str) -> str:
    return MATERIAL_MAP.get(material_name, "itu_concrete")


def _bsdf(parent: Element, bsdf_id: str) -> None:
    bsdf = SubElement(parent, "bsdf", {"type": "diffuse", "id": bsdf_id})
    SubElement(bsdf, "rgb", {"name": "reflectance", "value": "0.5 0.5 0.5"})


def _cube(
    parent: Element,
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    bsdf_ref: str,
) -> None:
    cx, cy, cz = center
    sx, sy, sz = size
    shape = SubElement(parent, "shape", {"type": "cube", "id": name})
    SubElement(shape, "ref", {"id": bsdf_ref})
    transform = SubElement(shape, "transform", {"name": "to_world"})
    # Mitsuba cube 預設是 [-1,1]^3 → scale 到 size/2，再平移到 center
    SubElement(transform, "scale", {
        "x": f"{sx/2:.4f}", "y": f"{sy/2:.4f}", "z": f"{sz/2:.4f}",
    })
    SubElement(transform, "translate", {
        "x": f"{cx:.4f}",
        "y": f"{cy+sy/2:.4f}",   # position[y]=0 代表建築底在地面，中心 y = sy/2
        "z": f"{cz:.4f}",
    })


def build_from_buildings(
    buildings: list[dict[str, Any]],
    ground: dict[str, Any] | None = None,
    integrator: str = "path",
) -> Element:
    """輸入 buildings[] 和可選 ground，產出 Mitsuba XML Element tree 根。

    buildings[] 每個 element 形狀：
        {"name": str, "position": [x,y,z], "size": [sx,sy,sz], "material": str}

    ground 形狀（可選）：
        {"position": [x,y,z], "size": [sx,sz]}
    """
    scene = Element("scene", {"version": "3.0.0"})
    SubElement(scene, "integrator", {"type": integrator})

    # 收集實際用到的材質
    used_materials = {b.get("material", "concrete") for b in buildings}
    used_materials.add("concrete")  # 地面預設

    itu_ids_emitted: set[str] = set()
    for m in used_materials:
        itu_id = _material_to_itu(m)
        if itu_id not in itu_ids_emitted:
            _bsdf(scene, itu_id)
            itu_ids_emitted.add(itu_id)

    # Ground
    g_size = tuple(ground.get("size", DEFAULT_GROUND_SIZE)) if ground else DEFAULT_GROUND_SIZE
    g_pos = tuple(ground.get("position", DEFAULT_GROUND_POSITION)) if ground else DEFAULT_GROUND_POSITION
    _cube(
        scene, "ground",
        center=(g_pos[0], g_pos[1] - 0.1, g_pos[2]),
        size=(g_size[0], 0.2, g_size[1]),
        bsdf_ref=_material_to_itu("concrete"),
    )

    # Buildings
    for i, b in enumerate(buildings):
        name = b.get("name", f"building_{i}")
        pos = b["position"]
        sz = b["size"]
        mat = b.get("material", "concrete")
        _cube(
            scene, name,
            center=(pos[0], pos[1], pos[2]),
            size=(sz[0], sz[1], sz[2]),
            bsdf_ref=_material_to_itu(mat),
        )

    return scene


def write_xml(scene_element: Element, out_path: str | Path) -> None:
    """把 scene Element 寫到檔案。"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tree = ElementTree(scene_element)
    indent(tree, space="  ")
    tree.write(out, encoding="utf-8", xml_declaration=True)


def build_and_write(
    buildings: list[dict[str, Any]],
    out_path: str | Path,
    ground: dict[str, Any] | None = None,
) -> str:
    """一次完成：buildings[] → XML → 寫檔。回傳最終檔案路徑字串。"""
    element = build_from_buildings(buildings, ground=ground)
    write_xml(element, out_path)
    return str(out_path)
