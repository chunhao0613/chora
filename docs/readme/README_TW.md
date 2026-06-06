<p align="center">
<img width="400" height="400" alt="icon" src="https://github.com/user-attachments/assets/9af6a6f6-17c9-46e8-b39d-9a37818baa14" />
</p>

# Thaumio: 輕量級物聯網行為與數據孿生引擎
**Thaumio** 是一個專為物聯網（IoT）設計、**基於非同步架構（Asynchronous）與配置驅動（Configuration-driven）**的輕量級物聯網行為與數據孿生引擎。

我們專注於數位孿生中的「數據與行為模擬 (Data & Behavioral Twin)」。Thaumio 免去了重型的 3D 視覺渲染與複雜的實體物理計算，而是為您的實體設備**在虛擬世界中建立具備狀態（Stateful）、因果連動邏輯（Correlation）與真實通訊協定（Protocols）的虛擬分身。**它是 IoT 後端服務、大數據平台、AI 異常預警模型進行**集成測試 (Integration Testing)** 與 **CI/CD 自動化流程**的完美沙箱工具。

## 💎 核心設計哲學 (Core Architecture)

### 1. 配置即代碼 (Configuration as Code)

Thaumio 採用完全聲明式（Declarative）的拓撲定義。您只需撰寫一份 `topology_config.json`，即可一鍵勾勒出龐大的物聯網拓撲（包含環境變數、閘道器、傳輸協議、設備規格、狀態更新公式與輸出 Payload 格式）。

* **強型別與語法輔助**：內建 `topology_schema.json`。在 VS Code/Cursor 等 IDE 中編輯設定檔時，享有自動補齊、語法防呆與即時報錯。
* **無縫安全對接**：原生支援生產環境所需的安全性憑證（TLS 雙向認證 mTLS、SAS Token、JWT）與動態 API。

### 2. 雙緩衝狀態求值 (Double-Buffered Stateful Modeling)

為了解決連續物理狀態（如：電池充放電、水庫水位增減）的精準模擬，Thaumio 獨創了**雙緩衝狀態求值機制**，徹底解決了業界常見的兩大痛點：

> **💡 消除 JSON 鍵值順序陷阱 (No Dictionary Ordering Trap)**
> 在標準 JSON 規範中物件是無序的。若公式 A 依賴公式 B 的結果，傳統順序求值器常因變數未定義而崩潰（尤其是被 Prettier 等工具按字母重排後）。Thaumio 在每 Tick 運算時，公式讀取的均是「上一時刻的狀態快照（Previous State）」，計算完畢後才一次性寫入。計算結果**完全不受 JSON 欄位排序影響**。
> **💡 消除遙測資料污染 (No Payload Pollution)**
> Thaumio 嚴格區分 `initial_state`、內部 `state_updates` 與最終輸出 `payload`。所有用於更新狀態的內部累加變數（如充電率、濾波中間值）僅保留在記憶體中，**不會**出現在發送給後端的遙測數據中，大幅節省頻寬與儲存成本。

### 3. 無洩漏物理隔離 (Zero-Leak Physics Isolation)

Thaumio 具備生產級的混沌工程故障注入（Chaos Injection）功能，能在模擬運行時透過 API，對環境變數強制注入自訂公式進行擾動（如：模擬颱風致使風速暴增、日蝕致使光照歸零）。

* **物理與混沌雙軌制**：環境內部獨立維護 `base_state`（純淨背景物理模擬）與 `state`（當前呈現狀態）。
* **零殘留恢復 (Zero-Leak Recovery)**：當混沌故障結束時，環境變數會**瞬間恢復至無中斷的真實物理數值**，完全不會對未來的物理模擬（如隨機漫步的累加基數）造成狀態洩漏與污染。

---

## 📊 數位孿生層次定位 (Digital Twin Matrix)

| 孿生層次 | 模擬內容 | 常用工具 | Thaumio 的定位 |
| --- | --- | --- | --- |
| **1. 視覺與幾何孿生** | 3D 外觀、管線走向、廠房建模 (BIM) | Unity, Unreal, AutoCAD | **不適用** ❌ (專注於後端與數據，無需渲染) |
| **2. 物理與力學孿生** | 材料疲勞、流體力學、風洞實驗 | ANSYS, COMSOL | **不適用** ❌ (無需消耗極大 CPU 計算力學碰撞) |
| **3. 數據與行為孿生** | **狀態機、因果邏輯、通訊協議與 mTLS** | 耗時自研模擬腳本 | **絕對主場** 🎯 (極輕量、Docker 一鍵啟動、配置驅動) |

---

## 🔌 企業級通訊適配器 (Enterprise Adapters)

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

我們提供兩種極致簡單的導入方式，滿足開發者與運維人員的不同需求：

### 方案 A：使用 PyPI 全域工具 (適合本地開發)

1. **安裝全域 CLI 工具**：
```bash
pip install thaumio
```
2. **一秒生成拓撲範本 (以智慧農場為例)**：
```bash
thaumio init --scenario smart_farm --out my_farm.json
```

3. **驗證設定檔 Schema**：
```bash
thaumio validate --config my_farm.json
```
4. **啟動模擬引擎 (將數據寫入本地 CSV)**：
```bash
thaumio run --config my_farm.json --output data/telemetry.csv
```

### 方案 B：使用 Docker 容器 (適合 CI/CD 與基礎設施整合)

1. **一鍵啟動 Thaumio 容器** (掛載設定檔並暴露 8081 控制面 API)：
```bash
docker run -d -p 8081:8081 
-v ./my_farm.json:/app/config/topology_config.json 
thaumio/thaumio:latest
```
2. **存取 Swagger 控制面文件**：
   開啟瀏覽器前往 `http://localhost:8081/docs` 即可管理運行中的孿生引擎。

---

## 📖 拓撲配置範例 (Topology Configuration)

以下為智慧路燈的配置範例，展示了**雙緩衝狀態累加**與**預定義混沌事件**的強大功能：

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

除了在設定檔中預先定義，您更可以隨時對運行中的容器注入**即時數學算式**進行故障演練：

### 觸發預定義事件 (例如：日蝕)

```bash
curl -X POST "http://localhost:8081/api/env/env_farm_01/event" \
     -H "Content-Type: application/json" \
     -d '{
       "event": "eclipse",
       "duration_sec": 15.0
     }'

```

### 動態注入即時算式 (On-the-fly Override)

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

## 🧪 Testcontainers CI/CD 整合測試

Thaumio 內建 `ThaumioContainer`。在後端 CI/CD 測試腳本（如 Pytest）中，您可以像啟動 Postgres 或 Redis 測試容器一樣，輕鬆拉起一個短暫的 Thaumio 數位孿生沙箱，完成自動化驗證：

```python
import pytest
import requests
from thaumio.utils.testcontainers import ThaumioContainer

def test_iot_telemetry_pipeline():
    # 1. 啟動 Thaumio 測試容器
    with ThaumioContainer(image="thaumio/thaumio:latest") as thaumio:
        api_url = thaumio.get_api_url()
        
        # 2. 驗證引擎狀態
        status_resp = requests.get(f"{api_url}/api/topology/status")
        assert status_resp.status_code == 200
        
        # 3. 在測試運行中，動態註冊測試用的感測器
        new_device = {
          "id": "dev_temp_sensor_test",
          "environment_id": "env_greenhouse_a",
          "gateway_id": "gw_primary",
          "update_interval_sec": 0.5,
          "payload": {
            "temperature_c": "env.base_temp"
          }
        }
        requests.post(f"{api_url}/api/topology/device", json=new_device)
        
        # 4. 注入極端高溫事件，驗證後端告警系統是否如期觸發
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
