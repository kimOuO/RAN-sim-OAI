"""場景頻率合法性探測。

把 Sionna ITU 材質的合法頻率範圍 (radio_materials/itu.py 的
ITU_MATERIALS_PROPERTIES) 跟 Mitsuba 場景實際載入的材質做交叉,
讓上層可以在「設頻率 → 觸發 ValueError → 偷偷 fallback」之前就主動
判定是否合法,並回給 client 明確的錯誤訊息(該場景能用哪些頻段)。

設計原則:
- 不替使用者改任何數字。不合就 raise SceneFrequencyMismatch。
- ITU 材質的範圍是靜態常數,可離線推算。
- Non-ITU(自訂)材質視為「無法靜態判定」,不擋,讓 Sionna runtime 自己驗。
- 部分 ITU 材質有不連續的頻率區間(例 glass: 0.1–100 ∪ 220–450 GHz),
  所以是用「逐 material 檢查 freq 是否落在它任一區間內」,而非單純取 min/max。
"""
from typing import Any


class SceneFrequencyMismatch(ValueError):
    """使用者設的頻率不在當前 Mitsuba 場景任一材質的有效範圍內。"""

    def __init__(
        self,
        freq_ghz: float,
        failing_materials: list[str],
        materials: dict[str, list[tuple[float, float]]],
    ):
        self.freq_ghz = freq_ghz
        self.failing_materials = failing_materials
        self.materials = materials
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        lines = [
            f"Frequency {self.freq_ghz} GHz is outside the valid range "
            f"for materials: {self.failing_materials}.",
            "Scene materials and their valid frequency ranges:",
            format_valid_ranges_message(self.materials),
        ]
        return "\n".join(lines)


def list_scene_materials(scene: Any) -> dict[str, list[tuple[float, float]]]:
    """列出場景使用的材質和它們各自的合法頻率範圍 (GHz)。

    Returns: {material_name: [(min_ghz, max_ghz), ...]}
        - ITU 材質會帶有真實 range list
        - Non-ITU(自訂)材質會回空 list,代表「範圍未知,不靜態擋」
    """
    # 延遲 import,避免 Django management command 也拖 Sionna kernel
    from sionna.rt.radio_materials.itu import ITU_MATERIALS_PROPERTIES

    out: dict[str, list[tuple[float, float]]] = {}
    for name in scene.radio_materials.keys():
        if name.startswith("itu_"):
            short = name[len("itu_"):]
            ranges = list(ITU_MATERIALS_PROPERTIES.get(short, {}).keys())
            out[name] = [(float(lo), float(hi)) for lo, hi in ranges]
        else:
            out[name] = []
    return out


def check_frequency_for_scene(
    freq_ghz: float, scene: Any
) -> tuple[bool, list[str], dict[str, list[tuple[float, float]]]]:
    """檢查 freq_ghz 對 scene 是否合法。

    Returns: (is_valid, failing_material_names, all_materials_with_ranges)

    is_valid 為 False 的條件:存在某個 ITU 材質,freq_ghz 不落在它「任何一個」
    有效區間內。Non-ITU 材質一律不擋(視為未知)。
    """
    materials = list_scene_materials(scene)
    failing = []
    for name, ranges in materials.items():
        if not ranges:
            continue
        if not any(lo <= freq_ghz <= hi for lo, hi in ranges):
            failing.append(name)
    return (len(failing) == 0, failing, materials)


def format_valid_ranges_message(
    materials: dict[str, list[tuple[float, float]]]
) -> str:
    """把材質清單格式化成人能看的一段訊息(給錯誤訊息 / API response 用)。"""
    lines = []
    for name, ranges in sorted(materials.items()):
        if not ranges:
            lines.append(f"  - {name}: range unknown (custom material)")
        else:
            r_str = ", ".join(f"{lo}–{hi} GHz" for lo, hi in ranges)
            lines.append(f"  - {name}: {r_str}")
    return "\n".join(lines)


def assert_frequency_for_scene(freq_ghz: float, scene: Any) -> None:
    """便利函式:不合法就直接 raise SceneFrequencyMismatch。"""
    ok, failing, materials = check_frequency_for_scene(freq_ghz, scene)
    if not ok:
        raise SceneFrequencyMismatch(freq_ghz, failing, materials)
