# Backend Architecture Specification 2.0 (Iron Rules)

本規範為**通用後端架構標準**，適用於任何基於 Django 的專案。所有 repo、路由、actors、serializers、models、services、tests、env 取得方式都必須符合，**不得自行發明、不准變形**。

---

## 0) 名詞定義（本規範用詞固定）

- **Repo**：一個後端系統的專案倉庫。
- **App**：`main/apps/<app_name>/` 這層 Django app（可多個）。
- **Actor**：HTTP handler + 統一入口，負責請求處理、數據驗證、調用 Service、錯誤處理、響應格式化。
- **Serializer**：資料驗證與轉換層，必須明確區分 Write / Read。
- **Model**：DB schema 的唯一落點，一個 table 對應一個檔案。
- **Service**：業務操作層，分為三類：
  - **Business Service**（必須）：提供單一職責的業務操作能力（創建實體、更新狀態、刪除數據、讀取數據等），供 Actor 調用編排。
  - **Common Service**（必須）：通用業務工具（UUID、Timestamp、Validation）。
  - **Optional Service**（按需）：特定領域邏輯（Calculation、Cache、Notification 等）。
- **Utils**：全專案共用基礎設施，**嚴禁放業務邏輯**。
- **Request Chain**：內部連接方式（本規範不可改）。

---

## 1) Repo 初始化模板（標準 Tree）鐵則

### 1-1 Repo 命名鐵則（ABSOLUTE）
- Repo 名稱**必須**是：`{platform.name}-{system.name}`
- 使用中線連接，不可使用底線
- 不可在 URL 中包含 system_name

### 1-2 標準目錄結構（不得刪減層級）

```
{platform.name}-{system.name}/
├── .dockerignore
├── .env
├── .env.sample
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── README.md
├── manage.py
├── requirements/
│   ├── base.txt
│   ├── local.txt
│   ├── production.txt
│   └── test.txt
├── logs/
│   └── .gitkeep
├── shell/
│   ├── init_project.sh
│   └── run_migrations.sh
└── main/
    ├── __init__.py
    ├── urls.py
    ├── asgi.py
    ├── wsgi.py
    ├── settings/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── local.py
    │   ├── production.py
    │   └── test.py
    ├── utils/
    │   ├── __init__.py
    │   ├── env_loader.py
    │   ├── logger.py
    │   ├── response.py
    │   └── db_router.py (多資料庫時)
    └── apps/
        └── <app_name>/
            ├── __init__.py
            ├── apps.py
            ├── models/
            │   ├── __init__.py
            │   └── <table_name>.py
            ├── serializers/
            │   ├── __init__.py
            │   └── <model>_serializers.py
            ├── actors/
            │   ├── __init__.py
            │   └── <model>_actor.py
            ├── api/
            │   ├── __init__.py
            │   ├── urls.py
            │   └── views.py (空殼保留)
            ├── services/
            │   ├── __init__.py
            │   ├── business/
            │   │   ├── __init__.py
            │   │   ├── <storage_type>_operations.py (資料存儲操作)
            │   │   ├── <function_category>_operations.py (功能目的操作，如需要)
            │   │   └── <system_name>_operations.py (外部系統操作，如需要)
            │   ├── common/
            │   │   ├── __init__.py
            │   │   ├── uuid_service.py
            │   │   ├── timestamp_service.py
            │   │   └── validation_service.py
            │   └── [optional]/
            │       └── calculation/
            │           └── <domain>_calculation.py
            └── tests/
                ├── __init__.py
                ├── services/
                └── unit_test/
```

> **鐵則**：tree 是制度，不是建議；任何 repo 必須符合此骨架。

---

## 2) 核心鐵則：Request Chain（內部連接方式）

### 2-1 請求鏈路（不可改）

```
Client 
  → main/urls.py 
  → app/api/urls.py 
  → Actor 
  → Serializer (驗證)
  → Business Service (業務編排)
  → Common Service (工具)
  → Model (資料庫)
  → Utils (基礎設施)
```

### 2-2 路由綁定鐵則（ABSOLUTE）

- `api/urls.py` **必須直接綁定 Actor function**
- `views.py` 層**可存在**但**不可成為必經層**（保留空殼）
- `main/urls.py` 只做路由聚合 `include(...)`，不可寫業務邏輯

> **鐵則**：任何 HTTP 路徑的最終 callable 必須是 `Actor.function`。

---

## 3) 每層級職責邊界（不可跨界）

### 3-1 Repo 根目錄職責

| 目錄/檔案 | 職責 |
|---------|------|
| `logs/` | 系統日誌存放（建議每日分檔） |
| `requirements/` | 依賴管理（base/local/production/test 分層） |
| `shell/` | 初始化與管理腳本 |
| `docker-compose.yml`, `Dockerfile` | 容器化配置 |

### 3-2 `main/` 職責

#### 3-2-1 `main/settings/` - 環境配置

- **必須分層**：`base.py` / `local.py` / `production.py` / `test.py`
- **禁止**直接使用 `os.getenv()`，必須透過 `env_loader`

#### 3-2-2 `main/urls.py` - 路由聚合

```python
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/", include("main.apps.<app_name>.api.urls")),
]
```

#### 3-2-3 `main/utils/` - 基礎設施工具箱

**必須包含的檔案**：
1. **env_loader.py** - 環境變數載入器（必須）
2. **logger.py** - 日誌配置（必須）
3. **response.py** - 響應格式標準化（必須）
4. **db_router.py** - 多資料庫路由器（多 DB 時必須）

**允許內容**：
- ✅ 日誌配置
- ✅ 環境變數管理
- ✅ 響應格式標準化
- ✅ 資料庫路由
- ✅ 通用錯誤處理

**禁止內容**：
- ❌ 業務邏輯（不得包含任何領域知識）
- ❌ Model 操作
- ❌ 業務驗證規則

**判定準則**：
```
問題：這段代碼應該放在 Utils 還是 Services？

1. 是否包含業務知識？
   是 → Services
   否 → 繼續

2. 是否可以直接複製到其他專案使用？
   是 → Utils
   否 → Services

3. 是否為框架級配置或技術基礎設施？
   是 → Utils
   否 → Services
```

### 3-3 `main/apps/<app>/` 職責

| 目錄 | 職責 | 說明 |
|------|------|------|
| `models/` | DB Schema 定義 | 一個 table 一個檔案 |
| `serializers/` | 數據驗證與轉換 | 必須區分 Write / Read |
| `actors/` | HTTP 處理 + 業務流程編排 | 驗證、編排、調用 Service、響應 |
| `services/business/` | 業務操作能力 | 提供單一業務操作（CRUD、狀態更新） |
| `services/common/` | 通用業務工具 | UUID、Timestamp、Validation |
| `services/[optional]/` | 特定領域邏輯 | 按需創建（Calculation 等） |
| `api/urls.py` | 路由配置 | 直接綁定 Actor |
| `api/views.py` | 空殼保留 | 不可成為必經層 |
| `tests/` | 測試 | services/ + unit_test/ |

### 3-4 Tests 分層鐵則

```
tests/
├── services/           # 測試 Service 層邏輯
│   └── test_<service_name>.py
└── unit_test/          # 測試 Actor API 行為
    ├── test_create.py
    ├── test_read.py
    ├── test_update.py
    └── test_delete.py
```

---

## 4) 空殼檔案最小內容（模板）

### 4-1 `main/apps/<app>/api/urls.py`

```python
from django.urls import path
from main.apps.<app_name>.actors.<model>_actor import <Model>Actor

urlpatterns = [
    path('<model>/create', <Model>Actor.create, name='<model>_create'),
    path('<model>/read', <Model>Actor.read, name='<model>_read'),
    path('<model>/update', <Model>Actor.update, name='<model>_update'),
    path('<model>/delete', <Model>Actor.delete, name='<model>_delete'),
]
```

### 4-2 `main/apps/<app>/api/views.py`

```python
# 空殼保留：非必經層
# Views layer is preserved but not required in request chain
```

### 4-3 `main/apps/<app>/actors/<model>_actor.py`

```python
class <Model>Actor:
    """Actor for <Model> CRUD operations"""
    pass
```

### 4-4 `main/apps/<app>/apps.py`

```python
from django.apps import AppConfig

class <AppName>Config(AppConfig):
    name = "main.apps.<app_name>"

    def ready(self):
        # 如需 signals，在此 import
        # import main.apps.<app_name>.services.signals
        pass
```

---

## 5) 生成規則（GENERATION RULES）

### 5-1 DB → Model 生成順序（ABSOLUTE）

1. **必須**以 Database tables 為基礎生成 `models/`
2. 每個 table 對應一個檔案：`models/<table_name>.py`
3. **禁止**合併多個 table 到同一檔案

### 5-2 Scenario → Actor function 推導

- 根據 Scenario 的 action，**自動推導** actor functions
- 每個 action 對應：
  - 一個 actor function
  - 一組 serializer（Write / Read，如需要）
- 命名規則：`create / read / update / delete / <custom_action>`

### 5-3 Business Service 生成規則（ABSOLUTE）

**核心原則**：Business Service **必須提供通用方法，而非為每個 Model 生成專門方法**。

#### 正確做法 ✅

```python
# services/business/sqldb_operations.py
class SqlDbBusinessService:
    @staticmethod
    def create_entity(model_class, validated_data):
        """通用創建方法，適用所有 Model"""
        return model_class.objects.create(**validated_data)
    
    @staticmethod
    def get_entity(model_class, uuid_field, uuid_value):
        """通用查詢方法"""
        return model_class.objects.get(**{uuid_field: uuid_value})

# Actor 調用範例
student = SqlDbBusinessService.create_entity(Students, student_data)
score = SqlDbBusinessService.create_entity(Score, score_data)
```

#### 錯誤做法 ❌

```python
# ❌ 為每個 Model 單獨寫方法（代碼臃腫）
class SqlDbBusinessService:
    @staticmethod
    def create_student(student_uuid, timestamp, **kwargs):
        return Students.objects.create(...)
    
    @staticmethod
    def create_score(score_uuid, timestamp, **kwargs):
        return Score.objects.create(...)
    
    @staticmethod
    def create_test(test_uuid, timestamp, **kwargs):
        return Test.objects.create(...)
    # 每個 Model 都重複一遍 → 臃腫且無通用性
```

#### 生成規則

1. **禁止為每個 Model 生成專門的 CRUD 方法**
2. **必須提供通用方法**，接受 `model_class` 作為參數
3. **Actor 負責**決定調用哪個 Model
4. **Serializer 的驗證規則**在 Actor 中調用，驗證後的數據傳給 Service

---

### 5-4 Actor 與 Service 協作模式（ABSOLUTE）

#### Actor 職責

1. **整合信息**：調用 Serializer 驗證數據
2. **準備參數**：組裝傳給 Service 的完整數據
3. **業務編排**：決定調用順序、選擇 Model class
4. **錯誤處理**：捕獲異常並返回響應

#### Service 職責

1. **提供通用方法**：不關心具體 Model
2. **執行操作**：接受參數並執行 CRUD
3. **返回結果**：返回 Model 實例或數據

#### 標準協作模式

```python
# Actor
class StudentActor:
    @staticmethod
    @transaction.atomic
    def create(request):
        # Step 1: 驗證數據（Actor 負責）
        serializer = StudentWriteSerializer(data=data)
        if not serializer.is_valid():
            return error_response("Validation failed", serializer.errors, 400)
        
        # Step 2: 準備完整數據（Actor 負責）
        validated_data = serializer.validated_data
        student_uuid = UUIDService.generate_uuid('student', validated_data['student_id'])
        timestamp = TimestampService.get_current_timestamp()
        
        entity_data = {
            'student_uuid': student_uuid,
            'student_created_at': timestamp,
            'student_updated_at': timestamp,
            **validated_data
        }
        
        # Step 3: 調用通用 Service（傳入 Model class）
        student = SqlDbBusinessService.create_entity(Students, entity_data)
        
        # Step 4: 創建關聯數據（Actor 編排）
        score_uuid = UUIDService.generate_uuid('score', student.student_id)
        score_data = {
            'score_uuid': score_uuid,
            'f_student_uuid': student_uuid,
            'score_created_at': timestamp,
            'score_updated_at': timestamp,
            'score_status': 'init'
        }
        SqlDbBusinessService.create_entity(Score, score_data)
        
        # Step 5: 格式化響應
        output = StudentReadSerializer(student).data
        return success_response(output, "Created successfully", 201)
```

---

### 5-5 Services 存在條件

- **Business Service**：必須存在（按操作對象分類，至少包含一個資料存儲類型）
- **Common Service**：必須存在（UUID、Timestamp、Validation）
- **Optional Service**：按需創建（根據專案需求決定）

### 5-6 禁止事項（ABSOLUTE）

- ❌ 嚴禁自行發明未在 input 出現的 table/action/scenario
- ❌ 嚴禁改動 Request Chain
- ❌ 嚴禁讓 views 成為主要入口
- ❌ 嚴禁使用 `os.getenv()`（只能透過 env_loader）
- ❌ **嚴禁為每個 Model 生成專門的 Service 方法**（必須使用通用方法）
- ❌ **嚴禁在 Service 中硬編碼 Model 名稱**（必須通過參數傳入）

---

## 6) 輸出順序鐵則（ABSOLUTE）

任何生成後端架構的產出，**必須依序輸出**：

1. Repo tree（完整目錄結構）
2. 每個 app 的內部結構說明
3. models/（每 table 一檔）
4. serializers/（Read / Write）
5. actors/（依 Scenario 生成）
6. services/（business + common + optional）
7. api/urls.py（路由綁定）
8. tests/（services + unit_test）
9. utils/（env_loader + logger + response）
10. settings/（環境配置）

> **鐵則**：順序不可變更，缺任一項視為不合格產出。

---

## 7) URL 與版本化規則

### 7-1 URL 格式
URL 格式一律為：

/api/{version}/{System}/{Module}/{Component}/{Element}

範例：
POST /api/v0.1/Calculus_oom/Calculus_metadata/Student_MetadataWriter/create
POST /api/v0.1/Calculus_oom/Calculus_metadata/Student_MetadataWriter/read
POST /api/v0.1/Calculus_oom/Calculus_metadata/Student_MetadataWriter/update
POST /api/v0.1/Calculus_oom/Calculus_metadata/Student_MetadataWriter/delete

參數定義（不可更名）
- {version}   : API 版本（v0.1 起）
- {System}    : 系統名稱（如 Calculus_oom）
- {Module}    : 模組名稱（如 Calculus_metadata）
- {Component} : Actor 名稱（如 Student_MetadataWriter）
- {Element}   : 動作名稱（create / read / update / delete / custom_action）
---

## 7-2 HTTP Method 規則（ABSOLUTE）

- **全系統所有 API 一律使用 POST**
- 包含：
  - Create
  - Read（查詢）
  - Update
  - Delete
  - Custom Action

- 不得使用 GET / PUT / PATCH / DELETE
- REST 語意由 {Element} 表達，而非 HTTP Method


## 8) 環境變數管理規則

### 8-1 .env 檔案

- `.env` 必須存在
- `.env.sample` 必須提供範例

### 8-2 Env Key 命名

```
# Django
DJANGO_SECRET_KEY=xxx
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb
DB_USER=user
DB_PASSWORD=password

# 跨模組 API
HTTP_<MODULE>_HOST=xxx
HTTP_<MODULE>_PORT=xxx
```

### 8-3 讀取規則（ABSOLUTE）

- **必須**透過 `from main.utils.env_loader import ...`
- **禁止**直接使用 `os.getenv()`

---

## 9) 落地驗收清單

專案是否符合本規範，檢查以下項目：

- [ ] Repo 名稱為 `{platform}-{system}`
- [ ] 目錄結構包含 logs/requirements/shell/main/settings/utils
- [ ] 路由為 `main/urls.py → app/api/urls.py → Actor.function`
- [ ] 每個 table 獨立一個 model 檔案
- [ ] Serializers 區分 Read/Write
- [ ] Services 包含 business/common/（optional）
- [ ] 所有 env 透過 env_loader 讀取
- [ ] Tests 包含 services/ 和 unit_test/

---

## 10) CORS 配置規則

### 10-1 套件（ABSOLUTE）

- 使用 `django-cors-headers`
- 加入 `requirements/base.txt`
- 配置在 `main/settings/<env>.py`

### 10-2 掛載

```python
# settings/base.py
INSTALLED_APPS = [
    ...
    "corsheaders",
    ...
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # 必須在 CommonMiddleware 之前
    "django.middleware.common.CommonMiddleware",
    ...
]
```

### 10-3 設定

```python
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True
```

---

## 11) 資料庫後端綁定規則

### 11-1 支援的資料庫（ABSOLUTE）

- PostgreSQL（預設）
- MySQL
- MongoDB (Djongo)

### 11-2 PostgreSQL/MySQL 規則

```python
from django.db import models

class Entity(models.Model):
    id = models.AutoField(primary_key=True)
    entity_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    ...
```

### 11-3 MongoDB (Djongo) 規則

```python
from djongo import models  # 注意：使用 djongo

class Entity(models.Model):
    _id = models.ObjectIdField(primary_key=True)  # 使用 _id
    entity_uuid = models.CharField(max_length=255, unique=True)
    ...
```

### 11-4 多資料庫規則

- **除非明確聲明**，否則禁止生成 `DATABASE_ROUTERS`
- 若使用多資料庫，必須在 `utils/db_router.py` 實現路由邏輯

---

## 12) Model 關聯規則

### 12-1 同資料庫關聯（使用 ForeignKey）

**適用條件**：兩個 Model 在同一資料庫

```python
class RelatedEntity(models.Model):
    parent = models.ForeignKey(
        'ParentEntity',
        on_delete=models.CASCADE,      # 級聯刪除
        to_field='entity_uuid',        # 關聯業務 UUID
        db_column='f_parent_uuid',     # 資料庫列名
        related_name='children',       # 反向查詢名稱
        db_index=True
    )
```

**on_delete 選項**：

| 選項 | 行為 | 適用場景 |
|------|------|---------|
| `CASCADE` | 刪除主記錄時自動刪除從記錄 | 用戶-訂單、專案-任務 |
| `PROTECT` | 有從記錄時禁止刪除主記錄 | 部門-員工 |
| `SET_NULL` | 刪除主記錄時設為 NULL | 可選關聯 |

### 12-2 跨資料庫關聯（使用 CharField）

**適用條件**：跨資料庫或跨實例

```python
class RelatedEntity(models.Model):
    f_parent_uuid = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Reference to parent entity UUID"
    )
```

**一致性維護（在 Business Service 實現）**：

```python
@transaction.atomic
def delete_entity_with_relations(entity_uuid):
    """刪除實體及關聯數據"""
    RelatedEntity.objects.filter(f_parent_uuid=entity_uuid).delete()
    ParentEntity.objects.filter(entity_uuid=entity_uuid).delete()
```

### 12-3 命名規則

| 關聯方式 | 欄位命名 | 範例 |
|---------|---------|------|
| ForeignKey | 語意化名稱 | `parent`, `user`, `order` |
| CharField | `f_<entity>_uuid` | `f_parent_uuid`, `f_user_uuid` |

---

## 13) Actor 職責規則（ABSOLUTE）

### 13-1 Actor 必須做的事情

1. **HTTP 請求處理**
   - 接收並解析請求（`json.loads(request.body)`）
   - 使用裝飾器（`@csrf_exempt`, `@require_http_methods`）

2. **數據驗證**
   - 調用 Serializer 驗證輸入
   - 處理驗證錯誤

3. **業務流程編排**（核心職責）
   - 決定業務操作的執行順序
   - 協調多個 Service 的調用
   - 處理跨 Model 操作邏輯
   - 控制 Transaction（使用 `@transaction.atomic`）
   - 實現業務規則判斷（if/else、狀態檢查）

4. **Service 調用**
   - 調用 Common Service 生成 UUID、Timestamp
   - 調用 Business Service 執行單一業務操作
   - 調用 Optional Service 執行特定邏輯

5. **錯誤處理與日誌**
   - 捕獲異常
   - 記錄日誌（`logger.info`, `logger.error`）
   - 返回標準化錯誤響應

6. **響應格式化**
   - 使用 Serializer 格式化輸出
   - 調用 `utils/response.py`

### 13-2 Actor 禁止做的事情

- ❌ 實現 UUID 生成算法（委託給 Common Service）
- ❌ 實現複雜計算邏輯（委託給 Optional Service）
- ❌ 直接使用 `Model.objects.create()`（委託給 Business Service）
- ❌ 使用 `os.getenv()`（使用 env_loader）
- ❌ 直接返回 `JsonResponse`（使用 utils/response.py）



### 13-4 判定準則

一個合格的 Actor function：

- ✅ 包含明確步驟：解析 → 驗證 → 業務編排 → 響應
- ✅ 完整錯誤處理
- ✅ 包含業務流程邏輯（順序控制、多 Service 協調）
- ✅ 不直接使用 `Model.objects.create()`（委託給 Business Service）

---

## 14) Service 分層規則（ABSOLUTE）

### 14-1 Service 目錄結構（強制）

```
services/
├── __init__.py
├── business/
│   ├── __init__.py
│   ├── sqldb_operations.py        # SQL DB 通用 CRUD
│   ├── nosqldb_operations.py      # MongoDB / NoSQL 通用操作
│   └── calculation_operations.py  # 功能型 Business Service（如需要）
├── common/
│   ├── __init__.py
│   ├── uuid_service.py
│   ├── timestamp_service.py
│   └── validation_service.py
└── optional/
    └── calculation/
```

---

### 14-2 Business Service（必須存在）

#### 定義

提供**針對特定操作對象的業務操作能力**，供 Actor 調用以完成業務流程編排。

**核心要求**：必須提供**通用方法**，避免為每個 Model 單獨編寫方法。

#### 通用性原則（CRITICAL）

**✅ 正確做法**：
- 一個 `create_entity(model_class, data)` 方法服務所有 Model
- Actor 傳入 Model class 和完整數據
- Service 不關心具體是哪個 Model

**❌ 錯誤做法**：
- 為每個 Model 寫專門方法：`create_student()`, `create_score()`, `create_test()`
- 結果：代碼臃腫，無通用性，維護困難
- 每新增一個 Model 就要加一組方法（create/get/update/delete）

#### 組織原則（ABSOLUTE）

一個 `.py` 檔案代表對**一個操作對象**的所有相關操作。

**操作對象分類原則**：

1. **資料存儲類型對象**
   - 按資料庫類型分類：關聯式 DB、文檔型 DB、鍵值型 DB
   - 檔名反映存儲類型：`<storage_type>_operations.py`
   
2. **功能目的類型對象**
   - 按業務功能分類：數據處理、格式轉換、統計分析
   - 檔名反映功能類別：`<function_category>_operations.py`

3. **外部系統類型對象**
   - 按對接系統分類：第三方服務、內部模組、外部 API
   - 檔名反映系統來源：`<system_name>_operations.py`

**命名建議**（不強制，根據專案調整）：
- 資料存儲：`relational_db.py`, `document_db.py`, `cache_store.py`
- 功能目的：`data_processing.py`, `format_conversion.py`, `analytics.py`
- 外部系提供通用的 CRUD 方法**（接受 Model class 作為參數）
2. **數據持久化**（Model.objects 操作）
3. **避免為每個實體單獨編寫方法**（保持代碼簡潔）

**關鍵原則**：
- ✅ **通用性**：一個 `create_entity()` 方法服務所有 Model
- ✅ **參數化**：通過傳入 Model class 和數據來區分不同實體
- ❌ **禁止**：為每個 Model 寫專門的方法（如 `create_student()`, `create_score()` 等

1. **對象內所有實體的 CRUD 操作**
2. **數據持久化**（Model.objects 操作）
3. **對象特定的業務規則**（狀態驗證、數據轉換）

#### 禁止職責

- ❌ 跨對象操作編排（由 Actor 負責）
- ❌ Transaction 控制（由 Actor 負責）
- ❌ 複雜業務流程決策（由 Actor 負責）

#### 命名規則

- **檔案**：`<object_category>.py` 或 `<object_category>_operations.py`
- **類**：`<ObjectCategory>BusinessService`
- **方法**：`<action>_<target>`
  - action: create, read, update, delete, process, convert, analyze 等
  - target: 操作的具體目標（實體名、數據類型等）



### 14-4 Optional Service（按需創建）

#### 創建條件

同時滿足以下條件時才創建：

1. ✅ 被多個 Business Service 使用（至少 2 個）
2. ✅ 邏輯內聚且獨立（可單獨測試）
3. ✅ 不適合放在 Common 或 Business

#### 常見類型

##### 1. Calculation Service

**適用場景**：
- 金融系統：利息計算、匯率轉換
- 評分系統：加權計算、統計分析
- 物流系統：運費計算、時效計算



##### 2. Cache Service

**適用場景**：Redis/Memcached 操作、頻繁讀取數據快取

##### 3. Notification Service

**適用場景**：郵件發送、SMS 通知、Push 通知

##### 4. Integration Service

**適用場景**：支付系統、地圖 API、社交媒體登入

---

### 14-5 Service 層禁止事項（ABSOLUTE）

所有 Service 層**禁止**：

1. ❌ 處理 HTTP（不得接收 request、返回 JsonResponse）
2. ❌ 直接驗證輸入（由 Serializer 負責）
3. ❌ 記錄業務日誌（由 Actor 負責，Service 可拋異常）
4. ❌ 控制 Transaction（由 Actor 使用 @transaction.atomic）
5. ❌ 跨 Model 操作編排（由 Actor 負責）
6. ❌ 業務流程決策（if/else 判斷由 Actor 負責）

---

### 14-6 Service 決策樹

```
問題：這段邏輯應該放在哪裡？

┌─ 1. 是否為 HTTP 請求/響應處理？
│     是 → Actor
│     否 → 繼續
│
├─ 2. 是否為數據驗證？
│     是 → Serializer
│     否 → 繼續
│
├─ 3. 是否為業務流程編排、跨 Model 操作、Transaction 控制？
│     是 → Actor
│     否 → 繼續
│
├─ 4. 是否為單一 Model 的 CRUD 操作？
│     是 → Business Service
│     否 → 繼續
│
├─ 5. 是否為通用工具（UUID、時間、驗證）？
│     是 → Common Service
│     否 → 繼續
│
├─ 6. 是否為技術基礎設施（Logger、Environment）？
│     是 → Utils
│     否 → 繼續
│
└─ 7. 是否為特定領域邏輯（計算、快取、通知）且被多個 Actor 使用？
      是 → Optional Service
      否 → 留在 Actor 內部
```

---