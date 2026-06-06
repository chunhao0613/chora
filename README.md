# Thaumio: Lightweight IoT Behavioral & Data Twin Engine

Thaumio 是一個專為物聯網（IoT）設計、非同步架構（Asynchronous）、配置驅動（Configuration-driven）的**輕量級物聯網行為與數據孿生引擎（Lightweight IoT Digital Twin）**。

Thaumio 專注於物聯網測試與模擬的第三層級——**「數據與行為孿生 (Data & Behavioral Twin)」**。它免去了重型的 3D 視覺渲染與複雜的機械受力計算，而是為您的物理設備在虛擬世界中建立具備**狀態（Stateful）**、**因果連動邏輯（Correlation）**與**真實通訊協定（Protocols）**的虛擬分身，是 IoT 後端服務、大數據平台、AI 異常預警模型進行**集成測試 (Integration Testing)** 與 **CI/CD 自動化流程**的終極沙箱工具。

---

## 💎 核心設計哲學 (Core Architecture Highlights)

### 1. ⚙️ 設定即代碼 (Configuration as Code)
Thaumio 採用完全聲明式（Declarative）的拓撲定義。您只需要撰寫一份 `topology_config.json`，即可勾勒出龐大的物聯網拓撲（包含環境、閘道器、傳輸協議、設備規格、狀態更新公式與輸出 Payload 格式）。
*   **強型別與語法輔助**：Thaumio 提供內建的 `topology_schema.json`。在 VS Code/Cursor 等 IDE 中編輯設定檔時，享有**自動補齊、語法防呆與即時報錯**。
*   **無痛盲接**：設定檔支援無縫對接生產環境所需的安全性憑證（TLS 雙向認證 mTLS、SAS Token、JWT）與動態 API。

### 2. 🔋 雙緩衝狀態累加 (Double-Buffered Stateful Modeling)
為了解決連續物理狀態（如：電池充放電、水庫水位增減）的狀態累加需求，Thaumio 獨創了**雙緩衝（Double-buffering）狀態求值機制**，徹底解決了以下兩大業界痛點：
> [!IMPORTANT]
> *   **消除 JSON 鍵值順序陷阱 (No Dictionary Ordering Trap)**：在標準 JSON 規範中物件是無序的。若公式 A 依賴公式 B 的結果，一旦 JSON 被格式化工具（如 Prettier）按字母重排，傳統順序求值器會因變數未定義而崩潰。Thaumio 在每 Tick 運算時，公式中讀取的均是「上一時刻的狀態快照（Previous State）」，計算完畢後才一次性更新寫入。因此計算結果**完全不受 JSON 欄位排序影響**。
> *   **消除遙測資料污染 (No Payload Pollution)**：Thaumio 將設備狀態區分為 `initial_state`、`state_updates`（內部狀態累加公式）與 `payload`（最終輸出）。所有用於更新狀態的內部累加變數（如：充電率、濾波中間值）僅保留在設備記憶體中，**不會**出現在最終發送給後端閘道器的遙測數據中，節省頻寬與儲存成本。

### 3. 🛡️ 無洩漏物理隔離 (Zero-Leak Physics Isolation)
Thaumio 具備生產級的**混沌工程故障注入（Chaos Injection）**功能，能在模擬運行時透過 API 或配置，對環境變數強制注入自訂公式進行擾動（如颱風致使風速暴增、日蝕致使光照歸零）。
> [!TIP]
> *   **物理與混沌雙軌制**：環境內部維護 `base_state`（純淨背景物理模擬）與 `state`（當前呈現狀態）。
> *   **零殘留恢復 (Zero-Leak Recovery)**：當混沌故障結束時，環境變數會**瞬間恢復至無中斷的真實物理數值**，完全不會對未來的物理模擬（如 Random Walk 隨機漫步的累加基數）造成任何殘留的狀態洩漏與污染。

---

## 📊 數位孿生的三個層次：Thaumio 的主場

| 孿生層次 | 模擬內容 | 常用工具 | Thaumio 的定位 |
| :--- | :--- | :--- | :--- |
| **1. 視覺與幾何孿生** | 3D 外觀、管線走向、廠房建模 (BIM) | Unity, Unreal, AutoCAD | **完全不碰** ❌（後端服務與資料庫不需要 3D 模型） |
| **2. 物理與力學孿生** | 材料疲勞、流體力學、風洞實驗 | ANSYS, COMSOL | **完全不碰** ❌（不需要消耗極大 CPU 進行物理碰撞計算） |
| **3. 數據與行為孿生** | **狀態機、因果邏輯、通訊協議與 mTLS** | 自研模擬腳本 | **絕對主場** 🎯（極輕量、Docker 一鍵啟動、JSON 即定義行為） |

---

## 🔌 生產級通訊適配器 (Enterprise Adapters)

Thaumio 內建了對主流物聯網雲端平台與時序資料庫的 Native 整合，無需在容器外額外撰寫轉接橋接器：
*   **本地落地**：CSV, JSONL, SQLite (支援異步線程安全 `check_same_thread=False` 鎖定)。
*   **傳輸協定**：標準 HTTP、MQTT (包含 mTLS 雙向認證)、Apache Kafka。
*   **雲端物聯網**：
    *   **AWS IoT Core** (`aws_iot`)：支援 X.509 憑證雙向認證與專屬 Topic 直推。
    *   **Azure IoT Hub** (`azure_iot`)：支援 SAS Token 驗證與裝置對雲端 (D2C) 遙測傳送。
    *   **GCP Pub/Sub** (`gcp_pubsub`)：支援 gRPC 協定與 Service Account 金鑰整合。
*   **時序資料庫**：
    *   **InfluxDB v2** (`influxdb`)：支援 InfluxDB Line Protocol 原生格式直寫。

---

## 🚀 快速開始 (Quick Start)

根據您的使用場景，Thaumio 提供了兩種極致簡單的免 git clone 導入軌道：

### 🛣️ 軌道一：使用 PyPI 全域工具 (開發者體驗與 Python 套件)
此方式適用於想要在本地快速撰寫拓撲、進行 Schema 驗證，或在 Python 測試代碼中 import Thaumio 物件的開發者。

1. **安裝全域 CLI 工具與套件**：
   ```bash
   pip install thaumio
   ```

2. **一秒生成智慧農場 (smart_farm) 拓撲範本**：
   ```bash
   thaumio init --scenario smart_farm --out my_farm.json
   ```

3. **強型別 Schema 驗證**（確保無欄位或格式錯誤）：
   ```bash
   thaumio validate --config my_farm.json
   ```

4. **啟動模擬引擎，直接將數據以 CSV 格式寫入本地**：
   ```bash
   thaumio run --config my_farm.json --output data/telemetry.csv
   ```

---

### 🛣️ 軌道二：使用 Docker Hub 執行環境 (運維與無 Python 環境)
此方式適用於不想處理 Python 環境、或需要在基礎設施與 CI 中直接啟動模擬器服務的場景。

1. **一鍵啟動 Thaumio 模擬引擎容器**：
   將您的設定檔掛載進容器，並對外暴露 8081 控制面 API：
   ```bash
   docker run -d -p 8081:8081 \
     -v ./my_farm.json:/app/config/topology_config.json \
     thaumio/thaumio:latest
   ```

2. **若需要掛載本地資料落腳點 (如 SQLite 或 CSV)**：
   ```bash
   docker run -d -p 8081:8081 \
     -v ./my_farm.json:/app/config/topology_config.json \
     -v ./data:/app/data \
     thaumio/thaumio:latest
   ```

*   **Swagger API 控制面文件**：`http://localhost:8081/docs`

---

## 📖 聲明式拓撲配置指南 (Topology Configuration)

以下為一個智慧路燈的配置範例，展示了 **雙緩衝狀態累加** 與 **預定義混沌事件** 的配置方式：

```json
{
  "dev_mode": true,
  "environments": [
    {
      "id": "env_farm_01",
      "name": "Smart Farm Sector A",
      "preset": "smart_farm",
      "chaos_events": {
        "eclipse": {
          "overrides": {
            "solar_radiation": "0.0"
          }
        }
      }
    }
  ],
  "gateways": [
    {
      "id": "gw_mqtt",
      "name": "Local EMQX Broker",
      "protocol": "mqtt",
      "endpoint": "mqtt://localhost:1883",
      "auth": {
        "type": "none"
      }
    }
  ],
  "devices": [
    {
      "id": "dev_solar_light_01",
      "name": "Solar Street Light 01",
      "type": "street_light",
      "environment_id": "env_farm_01",
      "gateway_id": "gw_mqtt",
      "update_interval_sec": 1.0,
      "initial_state": {
        "battery": 100.0,
        "charge_rate": 0.0
      },
      "state_updates": {
        "battery": "max(0.0, min(100.0, state.battery + state.charge_rate))",
        "charge_rate": "if env.solar_radiation > 200.0 then 2.0 else -1.0"
      },
      "payload": {
        "battery_level_pct": "state.battery",
        "charging_status": "state.charge_rate > 0.0"
      }
    }
  ]
}
```

---

## ⚡ 混沌故障動態注入 API (Chaos Control Plane)

除了在配置檔中預定義，您也可以隨時對運行中的 Thaumio 容器注入**自訂的即時數學算式**進行故障演練：

### A. 觸發預定義混沌事件
```bash
curl -X POST "http://localhost:8081/api/env/env_farm_01/event" \
     -H "Content-Type: application/json" \
     -d '{
       "event": "eclipse",
       "duration_sec": 15.0
     }'
```

### B. 注入動態即時數學公式 (On-the-fly Override)
```bash
curl -X POST "http://localhost:8081/api/env/env_farm_01/event" \
     -H "Content-Type: application/json" \
     -d '{
       "event": "solar_storm",
       "duration_sec": 30.0,
       "overrides": {
         "solar_radiation": "env.solar_radiation * 10.0",
         "cloud_cover": "0.0"
       }
     }'
```

---

## 🧪 Testcontainers 整合測試整合 (CI/CD)

Thaumio 內建的 `ThaumioContainer` 讓您在後端 CI/CD 的測試腳本（如 Pytest）中，能像使用 Postgres 或 Redis 測試容器一樣，輕鬆拉起一個短暫的 Thaumio 數位孿生沙箱：

```python
import pytest
import requests
from thaumio.utils.testcontainers import ThaumioContainer

def test_iot_telemetry_pipeline():
    # 1. 以兩行代碼拉起真實的 Thaumio 模擬容器
    with ThaumioContainer(image="thaumio/thaumio:latest") as thaumio:
        api_url = thaumio.get_api_url()
        
        # 2. 獲取當前拓撲狀態
        status_resp = requests.get(f"{api_url}/api/topology/status")
        assert status_resp.status_code == 200
        
        # 3. 在測試運行中，動態註冊一個測試用的新感測器
        new_device = {
          "id": "dev_temp_sensor_temp",
          "name": "Integration Test Temp Sensor",
          "type": "temperature",
          "environment_id": "env_greenhouse_a",
          "gateway_id": "gw_primary",
          "update_interval_sec": 0.5,
          "payload": {
            "temperature_c": "env.base_temp"
          }
        }
        reg_resp = requests.post(f"{api_url}/api/topology/device", json=new_device)
        assert reg_resp.status_code == 201
        
        # 4. 對環境注入高溫混沌事件，驗證後端告警系統是否正常觸發
        chaos_payload = {
            "event": "heatwave",
            "duration_sec": 5.0,
            "overrides": {
                "base_temp": "env.base_temp + 30.0"
            }
        }
        chaos_resp = requests.post(f"{api_url}/api/env/env_greenhouse_a/event", json=chaos_payload)
        assert chaos_resp.status_code == 200
```