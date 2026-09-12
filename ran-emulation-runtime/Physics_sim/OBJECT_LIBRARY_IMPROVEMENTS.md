# Object Library UI Improvements

## 📋 概览

改进了 RAN-sim 前端的物体选择流程，使用户能够：
- 从 Omniverse Platform 数据库中选择预定义的 USD 资产
- 根据对象类型编辑可配置字段
- 自动应用资产的默认值（大小、颜色、材质等）

## 🎯 改进内容

### 1. 新增配置文件：`fieldDefinitions.ts`

定义了所有可编辑字段、预设值和验证规则：

#### Sionna 支持的材质类型
```typescript
- itu_urban      // 城市环境
- itu_suburban   // 郊区环境
- itu_indoor     // 室内
- concrete       // 混凝土
- brick          // 砖
- steel          // 钢铁
- glass          // 玻璃
- grass          // 草地
- asphalt        // 沥青
```

#### gNB 频率预设（5G NR 频段）
```
n71  (617 MHz)   - 广覆盖 (20 MHz BW)
n41  (2.5 GHz)   - 中频段 (100 MHz BW)
n78  (3.5 GHz)   - 城市密集 (100 MHz BW) ⭐ 默认
n77  (3.8 GHz)   - 城市密集 (100 MHz BW)
n79  (4.7 GHz)   - 毫米波 (200 MHz BW)
```

**自动特性**：选择频率时自动设置推荐带宽

#### 对象类型的可编辑字段

**Building**
- name (必填)
- position [x, y, z] (必填，图表设置)
- size [x, y, z] (必填)
- color [r, g, b]
- rotation_xyz_deg [x, y, z]
- material (下拉选择 Sionna 材质)
- usd_path
- target_height_m

**gNB**
- name (必填)
- position [x, y, z] (必填，图表设置)
- frequency_ghz (下拉选择预设)
- bandwidth_mhz (自动设置)
- power_dbm (0-46)
- color [r, g, b]
- active (复选框)
- target_height_m

**UE**
- name (必填)
- position [x, y, z] (必填，图表设置)
- color [r, g, b]
- speed_mps (必填)

**Obstacle**
- name (必填)
- position [x, y, z] (必填，图表设置)
- size [x, y, z] (必填)
- color [r, g, b]
- material (下拉选择)
- usd_path

### 2. 改进 ObjectForm 组件

#### 两步流程

**Step 1: 选择物体库中的资产**
```
┌─────────────────────────────────────────┐
│  Select Building                        │
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │ Brownstone 02                       │ │
│ │ Elegant brownstone architecture     │ │
│ │ /omniverse/Library/...usda          │ │
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ Factory                             │ │
│ │ Industrial warehouse                │ │
│ │ /omniverse/Library/factory.usda     │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Step 2: 配置可编辑字段**
```
┌─────────────────────────────────────────┐
│  Configure Brownstone 02                │
├─────────────────────────────────────────┤
│ Name              [Building_01      ]   │
│ Position                                │
│   X: [0.0 ___] Y: [0.0 ___] Z: [0.0]  │
│ Size                                    │
│   X: [60 ___] Y: [80 ___] Z: [40 ___] │
│ Color (RGB slider)                      │
│   R: ████████░░ 0.80                    │
│   G: ██████░░░░ 0.60                    │
│   B: ████░░░░░░ 0.40                    │
│ Material: [ITU Urban ▼]                 │
│                                         │
│              [← Back]  [Create]         │
└─────────────────────────────────────────┘
```

#### 功能特性
- 资产卡片显示 label、description 和 USD 路径
- 选择资产自动应用默认值（default_size、default_color）
- 向量3输入（Position、Size、Rotation）
- RGB 颜色滑块 + 实时预览
- 下拉选择（Material、Frequency、Bandwidth）
- 自动帮助：GNB 频率改变时自动更新推荐的带宽
- 清晰的必填/可选字段标记

### 3. 改进的用户流程

```
Scene Page          Draw Page           Sim Page
─────────────────────────────────────────────────
┌─────────────┐
│Select Type  │──────────────┐
│(Building    │               │
│ gNB/UE)     │               │
└─────────────┘               │
         │                     │ (可选坐标调整)
         ↓                     │
┌──────────────────────────────────┐
│1. Select Preset from Library     │
│   (Browse available assets)      │
└──────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────┐
│2. Configure Editable Fields      │
│   (Name, Size, Color, Material)  │
│   Position: [0, 0, 0] (default)  │
└──────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────┐
│Created: Building_01              │──────→┌──────────────┐
│Created: gNB_1                    │        │ Draw Canvas  │
│Created: UE_Handover              │        │ (Set coords) │
└──────────────────────────────────┘        └──────────────┘
         │
         ↓
   [Next → Draw Page]
```

## 🔧 API 连接

### 数据流
```
RAN-sim Frontend
    ↓
omniverseClient.post('/api/v0.1/RAN/Assets/UsdAssetReader/list')
    ↓
Omniverse Platform (localhost:8001)
    ↓
Omniverse Platform DB (PostgreSQL)
    ↓
Returns: UsdAsset[] with:
  - asset_uuid
  - preset_id
  - object_type (building|gnb|ue|obstacle)
  - label
  - description
  - usd_path
  - default_size [x, y, z]
  - default_color [r, g, b]
  - default_scale [x, y, z]
```

## 📁 文件变更

| 文件 | 变更 |
|------|------|
| `frontend/config/fieldDefinitions.ts` | ✨ 新增 - 字段定义 |
| `frontend/components/ObjectForm.tsx` | 🔄 大幅改进 - 两步流程 + 动态字段 |
| `frontend/components/ObjectForm.module.css` | 🔄 改进 - 新的样式 |
| `frontend/app/page.tsx` | 🔄 小调整 - 表单数据处理 |

## 💡 使用示例

### 创建 Building

1. 点击 "🏢 Building" 卡片
2. 从库中选择 "Brownstone 02"
   - 自动应用默认尺寸 [60, 80, 40]
   - 自动应用默认颜色 [0.8, 0.6, 0.4]
3. 输入名称 "Building_A"
4. 选择材质 "itu_urban"
5. 点击 "Create"
6. 在 Draw 页面精确调整座标

### 创建 gNB

1. 点击 "📡 gNB" 卡片
2. 从库中选择 "Standard gNB"
3. 输入名称 "gNB_Macro_1"
4. 选择频率 "n78 (3.5 GHz)"
   - 自动设置带宽为 100 MHz
5. 调整功率 (0-46 dBm)，如 43
6. 点击 "Create"

## 🚀 优势

✅ **从数据库选择** - 不再硬编码或手动输入 USD 路径
✅ **预设默认值** - 减少用户输入，提高效率
✅ **智能表单** - 根据对象类型显示相关字段
✅ **可视化反馈** - 颜色预览、清晰的错误提示
✅ **遵循规范** - 严格按 EDITABLE_FIELDS.md 实现
✅ **座标灵活性** - 初始值在表单中，细调在 Draw 页面

## 📝 配置说明

### Sionna 材质

可根据需要扩展 `SIONNA_MATERIALS` 列表，Sionna 支持的材质包括：
- ITU 标准模型：itu_urban, itu_suburban, itu_indoor
- 建筑材料：concrete, brick, steel, glass
- 地表：grass, asphalt

### GNB 频率

可根据场景需要添加更多频段。当前支持 5G FR1 （0.6-6 GHz）。
扩展时更新：
1. `GNB_FREQUENCY_PRESETS`
2. `GNB_BANDWIDTH_PRESETS`

## 🐛 已知限制

- 座标初始值为 [0, 0, 0]，需在 Draw 页面精确设置
- 不支持在此流程中设置 waypoints（UE 轨迹），由 Draw 页面处理
- rotation_xyz_deg 需手动输入（暂无 UI 编辑器）

## 📌 后续改进

- [ ] 座标输入验证和范围检查
- [ ] Waypoint 编辑器在此页面或 Draw 页面
- [ ] 资产搜索/过滤功能
- [ ] 预设保存为模板
- [ ] 批量创建物体
