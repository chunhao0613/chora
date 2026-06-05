# 高擬真物聯網邊緣運算模擬系統 (Chora IoT Simulation System)

本系統是一套採用非同步架構（Asynchronous）、配置驅動（Configuration-driven）的輕量級合成數據產生器與物聯網模擬器。旨在高度還原「環境 ➔ 邊緣設備 ➔ 邊緣閘道器 ➔ 資料落地 (CSV/JSONL/SQLite) / 雲端 API」的真實拓樸結構。

Chora 常駐為守護進程（Daemon 微服務），具備動態拓樸 CRUD API、配置檔熱重載（Hot-Reloading）以及混沌工程故障注入能力，非常適合用於物聯網邊緣運算數據採集與 AI 訓練用合成數據生成。

---

## 🌟 核心特色 (Key Features)

1. **常駐微服務架構 (Daemonized Microservice)**：拔除執行時長限制，作為 Daemon 容器或行程常駐運行，支援標準的系統中斷訊號（SIGTERM）安全退出與資源釋放。
2. **動態拓樸 REST API (Dynamic Topology CRUD)**：提供 `/api/topology/*` 端點，支援在不重啟模擬器的情況下動態新增環境與邊緣設備，並可即時回傳整個系統的記憶體拓樸狀態。
3. **配置檔熱重載 (Config Hot-Reloading) 🔄**：引入 `watchdog` 套件，即時監聽設定檔。在不重啟系統或打 API 的情況下，修改設定檔即可在背景即時重新套用新的物理算式。
4. **多樣性本地資料落地 (Local Data Sinks) 💾**：新增兩種全新的輸出轉發器。除了支援 HTTP/MQTT/Kafka 外，更支援將產生的遙測與關聯性數據直接寫入本地的 `.csv` / `.jsonl` 檔案或 SQLite 資料庫（`.db`），讓 Chora 變身為強大的合成數據產生器（Synthetic Data Generator）。
5. **更高階的物理分佈引擎 (Advanced Distribution Engine) 📈**：
   - **馬可夫鏈 (Markov Chain)**：支援在環境變數配置隨機機率矩陣，例如模擬「天氣狀態」在「晴天 ➔ 多雲 ➔ 陣雨」之間依機率自然轉換。
   - **自訂條件公式**：支援在設定檔中編寫複雜的 Python 條件式（例如 `if env.cloud_cover > 0.5 then X else Y`），使沙箱求值器（SafeEvaluator）支援三元運算子。
6. **真實通訊與安全認證 (Real Protocols & Security)**：內建 HTTP/REST (aiohttp)、MQTT (paho-mqtt) 與 Kafka (aiokafka) 轉發適配器，並支援 mTLS (X.509) 與動態 JWT (RS256) 安全簽發認證。
7. **邊緣快取與斷線重連 (Edge Buffering & Recovery)**：閘道器模擬網絡隨機斷線。斷線時，遙測數據會自動緩衝至 FIFO 環形佇列；連線恢復時，自動批次補發。

---

## 📁 系統目錄結構 (Directory Structure)

```text
chora/
├── config/
│   └── topology_config.json      # 系統預設初始拓樸與物理公式設定
├── src/
│   ├── main.py                   # 模擬器守護進程與 Control Plane REST API 伺服器
│   ├── environment.py            # 物理引擎 (生成環境狀態變數、馬可夫鏈與混沌覆寫)
│   ├── device.py                 # 虛擬邊緣設備 (取樣環境並求值)
│   ├── gateway.py                # 邊緣閘道器 (數據聚合、快取與發送)
│   ├── adapters.py               # 協議轉發適配器 (HTTP, MQTT, Kafka, CSV, JSONL, SQLite)
│   └── utils/
│       ├── crypto_helper.py      # 安全認證輔助 (mTLS 自簽憑證與 jwt 金鑰對生成)
│       └── evaluator.py          # 沙箱安全算式求值引擎 (支援 ternary 條件運算子)
├── examples/
│   └── mock_server.py            # 測試用本機 Ingest 接收伺服器 (封存供參考)
├── Dockerfile                    # 容器化打包設定
├── docker-compose.yml            # 整合容器一鍵啟動檔
├── README.md                     # 本說明文件
└── requirements.txt              # 外部相依套件宣告
```

---

## 🚀 部署與執行說明 (Deployment & Getting Started)

### 方法一：使用 Docker Compose 啟動
這是最簡單的啟動方式，它會拉起 Chora 模擬引擎：
```bash
docker-compose up --build -d
```
* **Chora Engine API**: `http://localhost:8081`

### 方法二：本機 Python 執行
1. **安裝依賴套件**：
   ```bash
   pip install -r requirements.txt
   ```
2. **啟動模擬器守護進程**：
   ```bash
   python -m src.main --config config/topology_config.json
   ```
3. **將數據導出至本地檔案 (CSV/JSONL/SQLite) 💾**：
   ```bash
   # 輸出為 CSV 格式
   python -m src.main --config config/topology_config.json --output ./data/farm_dataset.csv
   
   # 輸出為 SQLite 資料庫
   python -m src.main --config config/topology_config.json --output ./data/farm_dataset.db
   ```

---

## 🎛️ 控制平面 REST API & 監控規格 (Control Plane API)

Chora 引擎的 Control Plane 監聽在 **`8081` 埠**：

### 1. 動態拓樸管理 API (Topology REST API)

* **查看即時拓樸狀態**：
  ```bash
  curl http://127.0.0.1:8081/api/topology/status
  ```
* **動態新增環境 (Environment)**：
  ```bash
  curl -X POST http://127.0.0.1:8081/api/topology/environment \
    -H "Content-Type: application/json" \
    -d '{
      "id": "env_dynamic_c",
      "name": "Dynamic Environment C",
      "update_interval_sec": 1.0,
      "state_variables": {
        "base_temp": {"type": "constant", "value": 25.0}
      }
    }'
  ```
* **動態新增邊緣設備 (Device)**：
  ```bash
  curl -X POST http://127.0.0.1:8081/api/topology/device \
    -H "Content-Type: application/json" \
    -d '{
      "id": "dev_dynamic_temp_01",
      "name": "Dynamic Temp Sensor 01",
      "type": "temp_sensor",
      "environment_id": "env_dynamic_c",
      "gateway_id": "gw_primary",
      "update_interval_sec": 1.0,
      "specs": {"offset": 0.5},
      "telemetry_rules": {
        "temperature": "env.base_temp + specs.offset + random.uniform(-0.1, 0.1)"
      }
    }'
  ```

### 2. 混沌工程注入 (Chaos Engineering)

在不停止模擬器的情況下，動態改變指定環境的物理參數：
```bash
# 注入 15 秒的颱風事件 (會自動最大化雲遮蔽率、飆升風速、並拉低氣溫)
curl -X POST http://127.0.0.1:8081/api/env/env_greenhouse_a/event \
  -H "Content-Type: application/json" \
  -d '{"event": "typhoon", "duration_sec": 15}'
```

---

## 🔒 安全性憑證管理 (Security & dev_mode)

為了降低測試門檻並確保安全性：
* 在配置檔 `topology_config.json` 中，若設有 `"dev_mode": true`，當 mTLS 或 JWT 憑證缺失時，Chora 會於啟動時**自動在本機生成測試憑證**。
* 若將 `"dev_mode": false`，Chora 會停用憑證生成功能，此時如缺少憑證將會拋出 `FileNotFoundError`，要求運維人員將憑證 Mount/掛載至 `/app/certs/` 對應路徑中。