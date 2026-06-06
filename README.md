# Thaumio: Lightweight IoT Behavioral & Data Twin Engine

other languages:[繁體中文](docs/readme/README_TW.md)

---

**Thaumio** is a lightweight, asynchronous, configuration-driven **IoT Behavioral and Data Twin Engine** designed specifically for the Internet of Things (IoT).

We focus strictly on the **"Data & Behavioral Twin"** layer of digital twin technology. Thaumio bypasses heavy 3D rendering and complex mechanical physics calculations. Instead, it creates virtual counterparts of your physical devices featuring **stateful persistence**, **causal correlation logic**, and **real-world communication protocols**. It serves as the ultimate sandbox for integration testing and CI/CD pipelines targeting IoT backend services, big data platforms, and AI anomaly detection models.

## 💎 Core Architecture Highlights

### 1. Configuration as Code

Thaumio utilizes a fully declarative topology definition. By simply writing a `topology_config.json`, you can instantiate massive IoT topologies—including environments, gateways, transport protocols, device specifications, state-update formulas, and payload formatting.

* **Strong Typing & IDE Assistance**: Ships with a built-in `topology_schema.json`. Enjoy autocomplete, syntax validation, and real-time error highlighting in IDEs like VS Code or Cursor.
* **Seamless Security Integration**: Natively supports production-grade security credentials out of the box, including Mutual TLS (mTLS), SAS Tokens, and JWTs.

### 2. Double-Buffered Stateful Modeling

To accurately simulate continuous physical states (e.g., battery charging/discharging, water reservoir levels), Thaumio introduces a **Double-Buffered State Evaluation Mechanism**, completely resolving two major industry pain points:

> **💡 Resolving the JSON Dictionary Ordering Trap**
> In standard JSON specifications, object keys are unordered. If Formula A depends on the result of Formula B, traditional sequential evaluators often crash due to undefined variables when formatters (like Prettier) alphabetically reorder keys. In Thaumio, formulas read from a "Previous State Snapshot" during each tick. Results are written all at once after calculation, making evaluations **100% immune to JSON key ordering**.
> **💡 Zero Payload Pollution**
> Thaumio strictly separates `initial_state`, internal `state_updates`, and the final output `payload`. Internal accumulator variables (like charge rates or smoothing filters) used for state updates remain safely in the device's memory. They are **never** injected into the final telemetry payload sent to the backend, drastically saving bandwidth and storage costs.

### 3. Zero-Leak Physics Isolation

Thaumio features a production-grade **Chaos Engineering Injection** module. You can inject custom mathematical formulas into environmental variables on the fly via API to simulate disruptions (e.g., a typhoon spiking wind speeds, or a solar eclipse dropping irradiance to zero).

* **Dual-Track Simulation**: Environments maintain an isolated `base_state` (pure background physics) alongside the active `state`.
* **Zero-Leak Recovery**: When a chaos event expires, the environment **instantly snaps back to the underlying continuous physical simulation**. There is absolutely no residual pollution or state leakage affecting future base physical calculations (like random walk bases).

---

## 📊 Digital Twin Matrix: Thaumio's Focus

| Twin Level | Simulation Scope | Common Tools | Thaumio's Position |
| --- | --- | --- | --- |
| **1. Visual & Geometric** | 3D models, pipelines, facility BIM | Unity, Unreal, AutoCAD | **Not Applicable** ❌ (Backends don't need 3D models) |
| **2. Physics & Mechanical** | Material fatigue, fluid dynamics | ANSYS, COMSOL | **Not Applicable** ❌ (Too CPU-heavy for data testing) |
| **3. Data & Behavioral** | **State machines, causal logic, mTLS** | Custom internal scripts | **Absolute Focus** 🎯 (Ultra-lightweight, Docker-ready) |

---

## 🔌 Enterprise Adapters

Thaumio comes with native integrations for mainstream IoT cloud platforms and time-series databases, eliminating the need for external bridge containers:

* **Local Storage**: CSV, JSONL, SQLite (with thread-safe async support).
* **Standard Protocols**: HTTP, MQTT (Full mTLS support), Apache Kafka.
* **Cloud IoT Services**:
* **AWS IoT Core** (`aws_iot`): X.509 certificate mTLS and dedicated topic routing.
* **Azure IoT Hub** (`azure_iot`): SAS Token authentication and D2C telemetry routing.
* **GCP Pub/Sub** (`gcp_pubsub`): gRPC protocol with Service Account JSON keys.


* **Time-Series Databases (TSDB)**:
* **InfluxDB v2** (`influxdb`): Direct writing using native InfluxDB Line Protocol.



---

## 🚀 Quick Start

We provide two frictionless deployment paths to suit both developers and DevOps engineers:

### Option A: PyPI Global Tool (For Local Development)

1. **Install the global CLI**:
```bash
pip install thaumio

```


2. **Generate a topology template (e.g., Smart Farm)**:
```bash
thaumio init --scenario smart_farm --out my_farm.json

```


3. **Validate the Schema**:
```bash
thaumio validate --config my_farm.json

```


4. **Run the simulation (Output to local CSV)**:
```bash
thaumio run --config my_farm.json --output data/telemetry.csv

```



### Option B: Docker Container (For CI/CD & Infrastructure)

1. **Start the Thaumio container with one command** (mounting config and exposing the API port):
```bash
docker run -d -p 8081:8081 \
  -v ./my_farm.json:/app/config/topology_config.json \
  thaumio/thaumio:latest

```


2. **Access the Swagger Control Plane**:
Open your browser and navigate to `http://localhost:8081/docs` to interact with the live twin engine.

---

## 📖 Topology Configuration Example

The following is an example of a smart street light, showcasing **double-buffered state updates** and **pre-defined chaos events**:

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

## ⚡ Chaos Control Plane API

In addition to pre-defined configurations, you can inject **on-the-fly mathematical overrides** into running containers to conduct fault drills:

### Trigger a Pre-defined Event (e.g., Eclipse)

```bash
curl -X POST "http://localhost:8081/api/env/env_farm_01/event" \
     -H "Content-Type: application/json" \
     -d '{
       "event": "eclipse",
       "duration_sec": 15.0
     }'

```

### Inject a Dynamic On-the-fly Formula

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

## 🧪 CI/CD Integration via Testcontainers

Thaumio includes a built-in `ThaumioContainer`. In your backend CI/CD test suites (like `pytest`), you can easily spin up an ephemeral Thaumio digital twin sandbox just as you would with a Postgres or Redis test container:

```python
import pytest
import requests
from thaumio.utils.testcontainers import ThaumioContainer

def test_iot_telemetry_pipeline():
    # 1. Spin up an ephemeral Thaumio testing container
    with ThaumioContainer(image="thaumio/thaumio:latest") as thaumio:
        api_url = thaumio.get_api_url()
        
        # 2. Validate engine status
        status_resp = requests.get(f"{api_url}/api/topology/status")
        assert status_resp.status_code == 200
        
        # 3. Dynamically register a test sensor during runtime
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
        
        # 4. Inject an extreme heatwave chaos event and assert backend alert triggers
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