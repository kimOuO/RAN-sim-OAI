"""產 PPT 用的精美場景視覺化圖（俯視 2D 場域 + 射線示意）。

用法:
    docker compose exec ranp-sim python3 /app/docs/slides/generate_scene_viz.py
或容器外:
    python3 docs/slides/generate_scene_viz.py
"""
import json
import math
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
from matplotlib.patheffects import withStroke

# ============ 風格設定（PPT 用大字、高解析度）============
FIG_SIZE = (16, 12)
DPI = 200
BG_COLOR = "#F5F7FA"
BUILDING_FILL = "#6C757D"
BUILDING_EDGE = "#343A40"
GROUND_COLOR = "#E8ECF1"
GNB_COLOR = "#DC3545"
GNB_COLOR_2 = "#0D6EFD"
GNB_COLOR_3 = "#198754"
UE_COLOR = "#FFC107"
LOS_COLOR = "#28A745"
REFLECT_COLOR = "#3B82F6"
DIFFRACT_COLOR = "#F59E0B"
BLOCKED_COLOR = "#EF4444"

# ============ 場景資料（對齊 scene_config.json）============
BUILDINGS = [
    {"name": "Office_NW", "pos": (-50, 50), "size": (30, 30), "material": "concrete"},
    {"name": "Commercial_NE", "pos": (50, 50), "size": (30, 30), "material": "concrete"},
    {"name": "Retail_SW", "pos": (-50, -50), "size": (30, 25), "material": "concrete"},
    {"name": "Apartment_SE", "pos": (50, -50), "size": (30, 30), "material": "concrete"},
    {"name": "Tower_Center", "pos": (0, 0), "size": (8, 8), "material": "concrete"},
    {"name": "Wall_South", "pos": (0, -100), "size": (140, 10), "material": "concrete"},
]

GNBS = [
    {"name": "gNB_Macro_NW", "pos": (-90, 90), "height": 30, "color": GNB_COLOR, "pci": 133},
    {"name": "gNB_Macro_SE", "pos": (90, -90), "height": 25, "color": GNB_COLOR_2, "pci": 135},
    {"name": "gNB_Small_Plaza", "pos": (20, 25), "height": 10, "color": GNB_COLOR_3, "pci": 137},
]

UES = [
    {"name": "UE_LOS_Ref", "pos": (15, 15), "label": "LoS 中心"},
    {"name": "UE_NLOS_Shadow", "pos": (-80, 30), "label": "NLOS 陰影"},
    {"name": "UE_Handover_Path", "pos": (-25, 30), "label": "換手路徑"},
    {"name": "UE_Cell_Edge", "pos": (0, -25), "label": "Cell 邊界"},
    {"name": "UE_Street_Canyon", "pos": (-40, -90), "label": "街谷"},
]


# ============ 繪圖輔助 ============

def setup_figure(title: str, subtitle: str = ""):
    """建一張標準場景俯視圖 figure。"""
    fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(GROUND_COLOR)

    # 畫場域邊界
    ax.add_patch(Rectangle((-125, -125), 250, 250,
                           facecolor=GROUND_COLOR,
                           edgecolor="#6C757D", linewidth=1.5, linestyle="--"))

    ax.set_xlim(-135, 135)
    ax.set_ylim(-135, 135)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.15, linestyle=":")
    ax.set_xlabel("X (公尺)  ←── 西 / 東 ──→", fontsize=13, color="#333")
    ax.set_ylabel("Z (公尺)  ←── 南 / 北 ──→", fontsize=13, color="#333")

    # Title + subtitle
    fig.suptitle(title, fontsize=22, fontweight="bold", color="#212529", y=0.95)
    if subtitle:
        ax.set_title(subtitle, fontsize=15, color="#495057", pad=15)

    # 指北針
    ax.annotate("N", xy=(120, 115), fontsize=20, fontweight="bold",
                ha="center", color="#495057")
    ax.annotate("↑", xy=(120, 103), fontsize=22, ha="center", color="#495057")

    return fig, ax


def draw_buildings(ax):
    """畫所有建築物（含陰影 + 材質標籤）。"""
    for b in BUILDINGS:
        x, z = b["pos"]
        w, d = b["size"]
        # 陰影（在 SE 方向偏移 3m）
        ax.add_patch(Rectangle((x - w/2 + 3, z - d/2 - 3), w, d,
                               facecolor="#000000", alpha=0.15, zorder=1))
        # 建築本體
        ax.add_patch(Rectangle((x - w/2, z - d/2), w, d,
                               facecolor=BUILDING_FILL,
                               edgecolor=BUILDING_EDGE, linewidth=2,
                               zorder=2))
        # 名稱標籤
        label = b["name"].replace("_", "\n")
        ax.text(x, z, label, ha="center", va="center", fontsize=9,
                color="white", fontweight="bold",
                path_effects=[withStroke(linewidth=2, foreground="#000000")],
                zorder=3)


def draw_gnb(ax, gnb, show_label=True, size=1.0):
    """畫 gNB（天線塔 icon + 圈圈 + 標籤）。"""
    x, z = gnb["pos"]
    c = gnb["color"]
    # 外圈光暈（表示發射範圍）
    for r, alpha in [(12 * size, 0.15), (8 * size, 0.25), (5 * size, 0.4)]:
        ax.add_patch(plt.Circle((x, z), r, color=c, alpha=alpha, zorder=4))
    # 中心點
    ax.plot(x, z, "^", markersize=18 * size, color=c,
            markeredgecolor="white", markeredgewidth=2, zorder=5)
    # 標籤
    if show_label:
        name = gnb["name"].replace("gNB_", "")
        ax.annotate(f"{name}\nPCI={gnb['pci']}",
                    xy=(x, z), xytext=(x, z - 15),
                    ha="center", fontsize=10, fontweight="bold", color=c,
                    bbox=dict(boxstyle="round,pad=0.3",
                              facecolor="white", edgecolor=c, linewidth=1.5),
                    zorder=6)


def draw_ue(ax, ue, show_label=True, highlight=False):
    """畫 UE（點 + 標籤）。"""
    x, z = ue["pos"]
    size = 16 if highlight else 10
    color = UE_COLOR if not highlight else "#FF6B35"
    ax.plot(x, z, "o", markersize=size, color=color,
            markeredgecolor="#333", markeredgewidth=2, zorder=5)
    if show_label:
        ax.annotate(ue["label"],
                    xy=(x, z), xytext=(x + 6, z + 6),
                    fontsize=9, color="#333",
                    bbox=dict(boxstyle="round,pad=0.25",
                              facecolor="#FFF9DB", edgecolor="#FFA500",
                              alpha=0.9),
                    zorder=6)


def draw_ray(ax, p1, p2, color, label=None, width=1.5, style="-", alpha=0.85):
    """在兩點間畫射線。"""
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
            linestyle=style, linewidth=width, color=color, alpha=alpha,
            zorder=7,
            path_effects=[withStroke(linewidth=width + 1.5, foreground="white")])
    if label:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my, label, fontsize=8, color=color, ha="center",
                bbox=dict(boxstyle="round,pad=0.2",
                          facecolor="white", edgecolor=color, alpha=0.9),
                zorder=8)


def add_legend(ax, items):
    """items = [(color, style, label)]"""
    handles = [Line2D([0], [0], color=c, linestyle=s, linewidth=2.5, label=label)
               for c, s, label in items]
    ax.legend(handles=handles, loc="upper left", fontsize=11,
              framealpha=0.95, edgecolor="#CED4DA", fancybox=True)


def add_info_box(ax, text, x=-125, y=-125, width=120, facecolor="#FFF9DB"):
    """在角落加說明框。"""
    ax.text(x, y, text, fontsize=11, color="#333",
            verticalalignment="bottom",
            bbox=dict(boxstyle="round,pad=0.8",
                      facecolor=facecolor, edgecolor="#FFA500", linewidth=1.5),
            zorder=10)


# ============ 產出各張圖 ============

def save(fig, fname):
    path = Path(__file__).parent / fname
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)
    print(f"  ✓ {fname}")


def slide_A_scene_layout():
    """A. 場景俯視圖（全景介紹）。"""
    fig, ax = setup_figure(
        "UMi 3-Sector 模擬場域俯視圖",
        "250m × 250m 街區，6 棟建築 + 3 個 gNB + 5 個 UE"
    )
    draw_buildings(ax)
    for gnb in GNBS:
        draw_gnb(ax, gnb)
    for ue in UES:
        draw_ue(ue=ue, ax=ax)

    # 圖例
    legend_elems = [
        mpatches.Patch(facecolor=BUILDING_FILL, edgecolor=BUILDING_EDGE, label="建築（concrete 材質）"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=GNB_COLOR,
               markersize=15, markeredgecolor="#333", label="gNB 基站"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=UE_COLOR,
               markersize=12, markeredgecolor="#333", label="UE 使用者"),
    ]
    ax.legend(handles=legend_elems, loc="upper right", fontsize=11,
              framealpha=0.95, fancybox=True)

    add_info_box(ax, "★ 座標系：Y 軸向上（高度），XZ 平面為地面\n"
                     "★ gNB 架在建築外（30m 高），UE 在地面 1.5m 高\n"
                     "★ 所有建築材質為 concrete（ITU-R P.2040-3）")
    save(fig, "A_scene_layout.png")


def slide_B_los_scenario():
    """B. LoS 情境：UE 中央看得到 gNB，多徑反射加總。"""
    fig, ax = setup_figure(
        "場景 B：LoS 直射 + 多徑反射",
        "UE_LOS_Reference 在中央廣場，gNB_Macro_NW 直射可見 + 建築反射"
    )
    draw_buildings(ax)
    for gnb in GNBS:
        draw_gnb(ax, gnb, size=0.7)

    target_ue = {"name": "UE_LOS_Reference", "pos": (15, 15), "label": "UE_LOS_Reference\nRSRP = -56 dBm"}
    draw_ue(ax, target_ue, highlight=True)

    tx = GNBS[0]["pos"]  # gNB_Macro_NW
    ue = target_ue["pos"]

    # 1. LoS 直射
    draw_ray(ax, tx, ue, LOS_COLOR, "LoS 直射路徑", width=3.5)

    # 2. 反射 1：經 Office_NW 外牆反射到 UE
    bounce1 = (-35, 50)  # Office_NW 東南角
    draw_ray(ax, tx, bounce1, REFLECT_COLOR, width=2.0, alpha=0.7)
    draw_ray(ax, bounce1, ue, REFLECT_COLOR, width=2.0, alpha=0.7)
    ax.plot(*bounce1, "s", markersize=10, color=REFLECT_COLOR,
            markeredgecolor="white", zorder=7)

    # 3. 反射 2：經 Tower_Center
    bounce2 = (-4, 4)
    draw_ray(ax, tx, bounce2, "#8B5CF6", width=1.5, alpha=0.65, style="--")
    draw_ray(ax, bounce2, ue, "#8B5CF6", width=1.5, alpha=0.65, style="--")
    ax.plot(*bounce2, "s", markersize=8, color="#8B5CF6",
            markeredgecolor="white", zorder=7)

    # 4. 反射 3：經 Commercial_NE
    bounce3 = (35, 50)
    draw_ray(ax, tx, bounce3, "#06B6D4", width=1.5, alpha=0.6, style=":")
    draw_ray(ax, bounce3, ue, "#06B6D4", width=1.5, alpha=0.6, style=":")

    add_legend(ax, [
        (LOS_COLOR, "-", "LoS 直射（主路徑，能量最強）"),
        (REFLECT_COLOR, "-", "1 階鏡面反射（Office_NW）"),
        ("#8B5CF6", "--", "1 階反射（Tower_Center）"),
        ("#06B6D4", ":", "1 階反射（Commercial_NE）"),
    ])

    add_info_box(ax,
                 "● 所有這些 path 的複數增益同時抵達 UE\n"
                 "● Sionna 把它們「相干加總」：h = Σ aᵢ\n"
                 "● RSRP = 43 dBm + 10·log10(|h|²) = -56 dBm\n"
                 "● 實際場景 Sionna 算到 ~35 條 path")
    save(fig, "B_los_multipath.png")


def slide_C_nlos_scenario():
    """C. NLOS 情境：UE 躲建築後，LoS 被擋 + 繞射救援。"""
    fig, ax = setup_figure(
        "場景 C：NLOS 陰影區（Office_NW 擋住 LoS）",
        "UE 躲在 Office_NW 後方，原本 LoS 被擋；靠繞射和反射接收"
    )
    draw_buildings(ax)
    for gnb in GNBS:
        draw_gnb(ax, gnb, size=0.7)

    target_ue = {"name": "UE_NLOS_Shadow", "pos": (-80, 30), "label": "UE_NLOS_Shadow\n躲在建築後"}
    draw_ue(ax, target_ue, highlight=True)

    tx_se = GNBS[1]["pos"]  # gNB_Macro_SE
    ue = target_ue["pos"]

    # 1. 被擋的 LoS（紅叉）
    midx, midy = (tx_se[0] + ue[0]) / 2, (tx_se[1] + ue[1]) / 2
    ax.plot([tx_se[0], ue[0]], [tx_se[1], ue[1]],
            linestyle="--", linewidth=2, color=BLOCKED_COLOR, alpha=0.5, zorder=4)
    ax.plot(-50, 50, "X", markersize=25, color=BLOCKED_COLOR,
            markeredgewidth=3, zorder=8)
    ax.text(-35, 55, "LoS 被\nOffice_NW 擋住", fontsize=11, color=BLOCKED_COLOR,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor=BLOCKED_COLOR, linewidth=1.5),
            zorder=9)

    # 2. 繞射路徑：過 Office_NW 東北角
    edge1 = (-35, 65)   # Office_NW 北邊緣
    draw_ray(ax, tx_se, edge1, DIFFRACT_COLOR, width=2.0, alpha=0.8)
    # 繞射彎道
    arc_pts = np.array([edge1, (-50, 55), (-65, 40), ue])
    ax.plot(arc_pts[:, 0], arc_pts[:, 1], color=DIFFRACT_COLOR,
            linewidth=2.0, alpha=0.85, zorder=7,
            path_effects=[withStroke(linewidth=3.5, foreground="white")])
    ax.plot(*edge1, "d", markersize=12, color=DIFFRACT_COLOR,
            markeredgecolor="white", markeredgewidth=1.5, zorder=8)
    ax.text(-35, 73, "Keller 繞射邊緣", fontsize=9,
            color=DIFFRACT_COLOR, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2",
                      facecolor="white", edgecolor=DIFFRACT_COLOR))

    # 3. 反射路徑：從 gNB_Macro_NW 反射
    tx_nw = GNBS[0]["pos"]
    draw_ray(ax, tx_nw, ue, LOS_COLOR, "NW 直射可通", width=3.0)
    ax.text(-60, 80, "gNB_Macro_NW 反而近\nLoS 可直通", fontsize=10,
            color=LOS_COLOR, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3",
                      facecolor="white", edgecolor=LOS_COLOR))

    add_legend(ax, [
        (BLOCKED_COLOR, "--", "被建築擋住的 LoS (被 X 劃掉)"),
        (DIFFRACT_COLOR, "-", "繞射路徑（Keller cone）"),
        (LOS_COLOR, "-", "其他 gNB 直通路徑"),
    ])

    add_info_box(ax,
                 "● 對 gNB_Macro_SE：LoS 被擋，只剩繞射 / 反射（RSRP = -85 dBm 偏弱）\n"
                 "● 對 gNB_Macro_NW：LoS 可直通（RSRP = -50 dBm 強）\n"
                 "● Sionna 會同時考慮所有 gNB 的所有 path\n"
                 "● 「serving_gnb」選 RSRP 最強的 → 這 UE 選 gNB_Macro_NW")
    save(fig, "C_nlos_diffraction.png")


def slide_D_cell_edge():
    """D. Cell Edge 干擾情境：UE 在兩基站中間被夾擊。"""
    fig, ax = setup_figure(
        "場景 D：Cell 邊界干擾區",
        "UE 在兩個 gNB 之間，neighbors[] 裡會出現多個 cell"
    )
    draw_buildings(ax)
    for gnb in GNBS:
        draw_gnb(ax, gnb, size=0.7)

    target_ue = {"name": "UE_Cell_Edge", "pos": (0, -25), "label": "UE_Cell_Edge\nSINR = 5 dB"}
    draw_ue(ax, target_ue, highlight=True)
    ue = target_ue["pos"]

    # 三 gNB 都有路徑到 UE
    # gNB_NW 是 serving（最強）
    draw_ray(ax, GNBS[0]["pos"], ue, LOS_COLOR, "serving (-63 dBm)", width=3.0)

    # gNB_SE / Plaza 是鄰居
    draw_ray(ax, GNBS[1]["pos"], ue, REFLECT_COLOR,
             "neighbor (-72 dBm, 差 9 dB)", width=2.2, style="--")
    draw_ray(ax, GNBS[2]["pos"], ue, DIFFRACT_COLOR,
             "neighbor (-75 dBm)", width=2.2, style=":")

    # 干擾圈
    circle = plt.Circle(ue, 20, facecolor="#EF4444", alpha=0.15,
                        edgecolor=BLOCKED_COLOR, linewidth=2, linestyle="--", zorder=3)
    ax.add_patch(circle)
    ax.text(ue[0] + 25, ue[1] - 15, "⚠ 干擾疊加區",
            fontsize=12, color=BLOCKED_COLOR, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3",
                      facecolor="white", edgecolor=BLOCKED_COLOR))

    add_legend(ax, [
        (LOS_COLOR, "-", "serving cell (gNB_NW, RSRP=-63)"),
        (REFLECT_COLOR, "--", "neighbor (gNB_SE, -72)"),
        (DIFFRACT_COLOR, ":", "neighbor (gNB_Plaza, -75)"),
    ])

    add_info_box(ax,
                 "● UE 同時收到 3 個 gNB 的訊號\n"
                 "● SINR = serving_S / (Σ neighbor_I + noise)\n"
                 "● serving - neighbor 差 < 6 dB → interfered = 1\n"
                 "● 這就是 A3 TTT handover 的觸發區")
    save(fig, "D_cell_edge.png")


def slide_E_ray_fan():
    """E. 10^6 rays 概念圖：gNB 往四面八方發射。"""
    fig, ax = setup_figure(
        "場景 E：gNB 發射 100 萬條射線（Fibonacci 球面取樣）",
        "俯視圖只畫 120 條示意；實際 3D 是往整個球面均勻發射"
    )
    draw_buildings(ax)
    for gnb in GNBS:
        draw_gnb(ax, gnb, size=0.7)
    for ue in UES:
        draw_ue(ax, ue, show_label=False)

    tx = GNBS[0]["pos"]
    # 畫 120 條射線（用 Fibonacci 方式在 2D 角度上取樣）
    golden = (1 + math.sqrt(5)) / 2
    N = 120

    for i in range(N):
        angle = 2 * math.pi * i / golden  # rad
        dx = math.cos(angle)
        dy = math.sin(angle)
        # ray 延伸到 250m 處（假設無碰撞）
        # 實際會撞建築——簡化處理：分 3 類顏色
        ray_end = (tx[0] + 250 * dx, tx[1] + 250 * dy)

        # 顏色依方向分類
        kind = i % 7
        if kind == 0:
            color, alpha, w = LOS_COLOR, 0.5, 1.2
        elif kind in (1, 2):
            color, alpha, w = REFLECT_COLOR, 0.25, 0.6
        else:
            color, alpha, w = "#9CA3AF", 0.15, 0.4

        ax.plot([tx[0], ray_end[0]], [tx[1], ray_end[1]],
                color=color, alpha=alpha, linewidth=w, zorder=3)

    # 重點標示
    ax.annotate("100 萬條射線均勻發射\n（圖示簡化為 120 條）",
                xy=tx, xytext=(tx[0] + 30, tx[1] - 30),
                fontsize=13, fontweight="bold", color="#212529",
                bbox=dict(boxstyle="round,pad=0.6",
                          facecolor="#FFF9DB", edgecolor="#FFA500", linewidth=2),
                arrowprops=dict(arrowstyle="->", color="#FFA500", lw=2),
                zorder=10)

    add_legend(ax, [
        (LOS_COLOR, "-", "射線 type A（示意）"),
        (REFLECT_COLOR, "-", "射線 type B（示意）"),
        ("#9CA3AF", "-", "射線 type C（示意）"),
    ])

    add_info_box(ax,
                 "● Fibonacci 球面取樣：100 萬條均勻覆蓋 4π 立體弧度\n"
                 "● 每條射線 = 電磁波傳播一個方向的代表（能量 20W/百萬 = 20μW）\n"
                 "● 90% 飛向天空 / 9% 被牆吸收 / 1% 抵達 UE → ~35 條真實 path\n"
                 "● GPU RT core 同時處理所有射線，~70 ms 完成")
    save(fig, "E_ray_emission.png")


def slide_F_coverage_heatmap():
    """F. Coverage heatmap：整個場域的 RSRP 熱圖。"""
    fig, ax = setup_figure(
        "場景 F：RSRP 覆蓋熱圖（gNB_Macro_NW）",
        "格點 5m×5m，每格算 Sionna path gain → RSRP"
    )

    # 生成假的熱圖資料（符合物理直覺）
    grid_x = np.arange(-125, 126, 5)
    grid_z = np.arange(-125, 126, 5)
    X, Z = np.meshgrid(grid_x, grid_z)

    # FSPL-based RSRP（考慮距離 + 建築遮蔽）
    tx = GNBS[0]["pos"]
    d = np.sqrt((X - tx[0])**2 + (Z - tx[1])**2 + 30**2)
    rsrp = 43 - (20 * np.log10(d) + 20 * np.log10(3500) - 27.55)

    # 模擬建築遮蔽 —— 建築正後方 RSRP 扣 20 dB
    for b in BUILDINGS:
        bx, bz = b["pos"]
        bw, bd = b["size"]
        dx = X - tx[0]
        dz = Z - tx[1]
        # UE 位置相對 gNB 方向
        # 如果 UE 在建築後方（建築跟 TX 方向在同一邊）
        gnb_to_b_x = bx - tx[0]
        gnb_to_b_z = bz - tx[1]
        gnb_to_ue_x = dx
        gnb_to_ue_z = dz
        # 點積檢查是否在遮蔽區
        dot = gnb_to_b_x * gnb_to_ue_x + gnb_to_b_z * gnb_to_ue_z
        # UE 是否在建築矩形內後面
        mask = (
            (np.abs(X - bx) < bw / 2 + 5) &
            (np.abs(Z - bz) < bd / 2 + 5) &
            (dot > gnb_to_b_x**2 + gnb_to_b_z**2)
        )
        rsrp = np.where(mask, rsrp - 25, rsrp)

    rsrp = np.clip(rsrp, -110, -30)

    # 底色先鋪成白（避免被 facecolor 混色）
    ax.set_facecolor("white")
    mesh = ax.pcolormesh(X, Z, rsrp, cmap="RdYlGn",
                         vmin=-105, vmax=-40, shading="auto", zorder=1)
    cbar = plt.colorbar(mesh, ax=ax, label="RSRP (dBm)",
                 shrink=0.7, pad=0.02)
    cbar.ax.tick_params(labelsize=11)

    # 建築放熱圖上面但半透明讓熱圖看得到
    for b in BUILDINGS:
        x, z = b["pos"]
        w, d = b["size"]
        ax.add_patch(Rectangle((x - w/2, z - d/2), w, d,
                               facecolor=BUILDING_FILL,
                               edgecolor=BUILDING_EDGE, linewidth=2,
                               alpha=0.85, zorder=3))
        label = b["name"].replace("_", "\n")
        ax.text(x, z, label, ha="center", va="center", fontsize=8,
                color="white", fontweight="bold",
                path_effects=[withStroke(linewidth=2, foreground="#000000")],
                zorder=4)
    draw_gnb(ax, GNBS[0], size=0.8)
    # 其他 gNB 淡化
    for gnb in GNBS[1:]:
        x, z = gnb["pos"]
        ax.plot(x, z, "^", markersize=12, color=gnb["color"],
                markeredgecolor="white", alpha=0.4, zorder=4)

    add_info_box(ax,
                 "● 顏色：綠 = 訊號強（近 gNB）；紅 = 訊號弱（遠 / 被遮）\n"
                 "● 建築後方明顯陰影（RSRP 下降 20+ dB）\n"
                 "● Sionna RadioMapSolver() 一次算整張圖（~200 ms）\n"
                 "● 用於覆蓋率統計 / gNB 擺放研究 / UI 熱圖可視化")
    save(fig, "F_coverage_heatmap.png")


def _configure_cjk_font():
    """強制 matplotlib 使用 Noto CJK 字型（host 的 .ttc 檔）。"""
    import matplotlib.font_manager as fm
    # 強制重建 font cache（新裝 font 後必做一次）
    try:
        fm.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    except Exception:
        pass
    # 也試 bold
    try:
        fm.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
    except Exception:
        pass

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "Noto Sans CJK TC", "Noto Sans CJK SC", "Noto Sans CJK JP",
        "Noto Sans CJK HK", "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


if __name__ == "__main__":
    _configure_cjk_font()

    print("產 PPT 用場景圖...")
    slide_A_scene_layout()
    slide_B_los_scenario()
    slide_C_nlos_scenario()
    slide_D_cell_edge()
    slide_E_ray_fan()
    slide_F_coverage_heatmap()
    print("完成 6 張圖 → docs/slides/*.png")
