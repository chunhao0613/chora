import os
import ssl
import time
import json
import asyncio
import logging
import jwt
import csv
import sqlite3
from typing import Optional

# Dynamically import protocol clients
try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

try:
    import aiokafka
except ImportError:
    aiokafka = None

from src.utils.crypto_helper import ensure_test_credentials, generate_ephemeral_rsa_key
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger("ProtocolAdapters")

class BaseAdapter:
    async def connect(self):
        """Initializes connection and performs cryptographic/protocol handshakes."""
        raise NotImplementedError

    async def send(self, payload: dict) -> bool:
        """Sends aggregated telemetry. Returns True if successful, raises exception if failed."""
        raise NotImplementedError

    async def close(self):
        """Cleans up sockets and connections."""
        raise NotImplementedError


class HTTPAdapter(BaseAdapter):
    def __init__(self, config: dict):
        self.config = config
        self.endpoint = config.get("endpoint", "http://localhost:8080/api/telemetry")
        self.auth_config = config.get("auth", {})
        self.auth_type = self.auth_config.get("type", "none").lower()
        self.handshake_delay = self.auth_config.get("handshake_delay_sec", 0.0)
        self.session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        if not aiohttp:
            raise ImportError("aiohttp is required for HTTPAdapter but not installed.")

        # Simulate Handshake latency
        if self.handshake_delay > 0:
            logger.info(f"Simulating HTTP secure handshake delay ({self.handshake_delay}s)...")
            await asyncio.sleep(self.handshake_delay)

        ssl_ctx = None
        headers = {"Content-Type": "application/json"}

        # 1. Setup TLS/mTLS
        if self.auth_type == "mtls":
            cert_file = self.auth_config.get("cert_file", "certs/client.crt")
            key_file = self.auth_config.get("key_file", "certs/client.key")
            ca_file = self.auth_config.get("ca_file", "certs/ca.crt")
            
            dev_mode = self.config.get("dev_mode", False)
            ensure_test_credentials(cert_file, key_file, ca_file, dev_mode=dev_mode)
            
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
            if os.path.exists(ca_file):
                ssl_ctx.load_verify_locations(cafile=ca_file)
            logger.info("HTTPAdapter: mTLS credentials configured successfully.")

        # 2. Setup JWT
        elif self.auth_type == "jwt":
            token = self._resolve_jwt_token()
            headers["Authorization"] = f"Bearer {token}"
            logger.info("HTTPAdapter: JWT Authorization headers configured.")

        # Create ClientSession
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        self.session = aiohttp.ClientSession(connector=connector, headers=headers)
        logger.info(f"HTTPAdapter: Client Session initialized to endpoint '{self.endpoint}'")

    def _resolve_jwt_token(self) -> str:
        # Check if direct token is provided
        if "token" in self.auth_config:
            return self.auth_config["token"]
        
        # Check if token file is provided
        token_file = self.auth_config.get("token_file")
        if token_file and os.path.exists(token_file):
            with open(token_file, "r") as f:
                return f.read().strip()
                
        # Generate token dynamically using private key or ephemeral key
        logger.info("Generating dynamic JWT for HTTP adapter authentication.")
        private_key_file = self.auth_config.get("private_key_file", "certs/device.key")
        
        # Claims
        payload = {
            "iss": self.auth_config.get("issuer", "chora-gateway"),
            "aud": self.auth_config.get("audience", "iot-hub"),
            "iat": int(time.time()),
            "exp": int(time.time()) + self.auth_config.get("token_ttl_sec", 300)
        }
        
        if private_key_file and os.path.exists(private_key_file):
            with open(private_key_file, "rb") as f:
                private_key = serialization.load_pem_private_key(f.read(), password=None)
        else:
            logger.warning("Private key file not found. Generating ephemeral RSA private key for JWT signing.")
            private_key = generate_ephemeral_rsa_key()
            
        return jwt.encode(payload, private_key, algorithm="RS256")

    async def send(self, payload: dict) -> bool:
        if not self.session:
            raise RuntimeError("HTTP Session is not connected. Call connect() first.")
        
        async with self.session.post(self.endpoint, json=payload) as response:
            if response.status in [200, 201, 202]:
                return True
            else:
                logger.error(f"HTTP Server returned status {response.status}: {await response.text()}")
                return False

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None


class MQTTAdapter(BaseAdapter):
    def __init__(self, config: dict):
        self.config = config
        self.host = config.get("endpoint", "localhost")
        self.port = config.get("port", 1883)
        self.topic = config.get("topic", "telemetry/chora")
        self.auth_config = config.get("auth", {})
        self.auth_type = self.auth_config.get("type", "none").lower()
        self.handshake_delay = self.auth_config.get("handshake_delay_sec", 0.0)
        
        self.client = None
        self.loop = None
        self.connected_future = None

    async def connect(self):
        if not mqtt:
            raise ImportError("paho-mqtt is required for MQTTAdapter but not installed.")

        # Simulate Handshake latency
        if self.handshake_delay > 0:
            logger.info(f"Simulating MQTT secure handshake delay ({self.handshake_delay}s)...")
            await asyncio.sleep(self.handshake_delay)

        self.loop = asyncio.get_running_loop()
        self.connected_future = self.loop.create_future()

        # Handle paho-mqtt v2.x vs v1.x client version checks
        try:
            self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            self.client = mqtt.Client()

        # Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        # Config mTLS
        if self.auth_type == "mtls":
            cert_file = self.auth_config.get("cert_file", "certs/client.crt")
            key_file = self.auth_config.get("key_file", "certs/client.key")
            ca_file = self.auth_config.get("ca_file", "certs/ca.crt")
            
            dev_mode = self.config.get("dev_mode", False)
            ensure_test_credentials(cert_file, key_file, ca_file, dev_mode=dev_mode)
            
            self.client.tls_set(
                ca_certs=ca_file if os.path.exists(ca_file) else None,
                certfile=cert_file,
                keyfile=key_file
            )
            logger.info("MQTTAdapter: TLS certificates loaded for mTLS.")

        # Config JWT / Credentials
        elif self.auth_type == "jwt":
            token = self._resolve_jwt_token()
            # Pass JWT as password, username can represent client metadata
            self.client.username_pw_set(username="jwt_auth", password=token)
            logger.info("MQTTAdapter: JWT Token configured for username/password authentication.")

        logger.info(f"MQTTAdapter: Connecting to MQTT Broker at {self.host}:{self.port}...")
        self.client.connect_async(self.host, self.port, keepalive=60)
        self.client.loop_start()

        # Wait for on_connect to complete with a 10s timeout
        try:
            await asyncio.wait_for(self.connected_future, timeout=10.0)
            logger.info("MQTTAdapter: Successfully authenticated and connected.")
        except asyncio.TimeoutError:
            self.client.loop_stop()
            raise ConnectionError(f"Timeout connecting to MQTT Broker at {self.host}:{self.port}")

    def _resolve_jwt_token(self) -> str:
        if "token" in self.auth_config:
            return self.auth_config["token"]
        
        token_file = self.auth_config.get("token_file")
        if token_file and os.path.exists(token_file):
            with open(token_file, "r") as f:
                return f.read().strip()
                
        # Generate token dynamically
        private_key_file = self.auth_config.get("private_key_file", "certs/device.key")
        payload = {
            "iss": self.auth_config.get("issuer", "chora-gateway"),
            "aud": self.auth_config.get("audience", "emqx-broker"),
            "iat": int(time.time()),
            "exp": int(time.time()) + self.auth_config.get("token_ttl_sec", 300)
        }
        
        if private_key_file and os.path.exists(private_key_file):
            with open(private_key_file, "rb") as f:
                private_key = serialization.load_pem_private_key(f.read(), password=None)
        else:
            private_key = generate_ephemeral_rsa_key()
            
        return jwt.encode(payload, private_key, algorithm="RS256")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        # rc is connection result (0 is success)
        # Note: in paho-mqtt v2, rc is a ReasonCode object which evaluates to rc.value or rc
        rc_code = rc.value if hasattr(rc, "value") else rc
        if rc_code == 0:
            self.loop.call_soon_threadsafe(self.connected_future.set_result, True)
        else:
            err = ConnectionError(f"MQTT Connection failed with return code: {rc}")
            self.loop.call_soon_threadsafe(self.connected_future.set_exception, err)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        logger.warning(f"MQTTAdapter: Disconnected from broker. Code: {rc}")

    async def send(self, payload: dict) -> bool:
        if not self.client or not self.client.is_connected():
            raise ConnectionError("MQTT Client is disconnected.")

        # Publish payload
        msg_info = self.client.publish(self.topic, json.dumps(payload), qos=1)
        
        # Wait for publish in a thread-safe future wrapper
        fut = self.loop.create_future()
        
        def check_published():
            try:
                msg_info.wait_for_publish(timeout=3.0)
                self.loop.call_soon_threadsafe(fut.set_result, True)
            except Exception as e:
                self.loop.call_soon_threadsafe(fut.set_exception, e)

        # Run wait_for_publish in executor since it is blocking
        asyncio.create_task(self.loop.run_in_executor(None, check_published))
        
        try:
            return await fut
        except Exception as e:
            logger.error(f"MQTT Publish failed: {e}")
            return False

    async def close(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None


class KafkaAdapter(BaseAdapter):
    def __init__(self, config: dict):
        self.config = config
        self.bootstrap_servers = config.get("endpoint", "localhost:9092")
        self.topic = config.get("topic", "telemetry-chora")
        self.auth_config = config.get("auth", {})
        self.auth_type = self.auth_config.get("type", "none").lower()
        self.handshake_delay = self.auth_config.get("handshake_delay_sec", 0.0)
        self.producer = None

    async def connect(self):
        if not aiokafka:
            raise ImportError("aiokafka is required for KafkaAdapter but not installed.")

        # Simulate Handshake latency
        if self.handshake_delay > 0:
            logger.info(f"Simulating Kafka secure handshake delay ({self.handshake_delay}s)...")
            await asyncio.sleep(self.handshake_delay)

        ssl_ctx = None
        security_protocol = "PLAINTEXT"

        # Setup TLS/mTLS
        if self.auth_type == "mtls":
            cert_file = self.auth_config.get("cert_file", "certs/client.crt")
            key_file = self.auth_config.get("key_file", "certs/client.key")
            ca_file = self.auth_config.get("ca_file", "certs/ca.crt")
            
            dev_mode = self.config.get("dev_mode", False)
            ensure_test_credentials(cert_file, key_file, ca_file, dev_mode=dev_mode)
            
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
            if os.path.exists(ca_file):
                ssl_ctx.load_verify_locations(cafile=ca_file)
            security_protocol = "SSL"
            logger.info("KafkaAdapter: SSL context configured for mTLS.")

        self.producer = aiokafka.AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            security_protocol=security_protocol,
            ssl_context=ssl_ctx
        )
        await self.producer.start()
        logger.info(f"KafkaAdapter: Producer started and connected to {self.bootstrap_servers}")

    async def send(self, payload: dict) -> bool:
        if not self.producer:
            raise RuntimeError("Kafka Producer is not started. Call connect() first.")
        
        value_bytes = json.dumps(payload).encode("utf-8")
        await self.producer.send_and_wait(self.topic, value=value_bytes)
        return True

    async def close(self):
        if self.producer:
            await self.producer.stop()
            self.producer = None


class CSVAdapter(BaseAdapter):
    def __init__(self, config: dict):
        self.config = config
        self.filepath = config.get("endpoint", "telemetry.csv")

    async def connect(self):
        await asyncio.to_thread(self._init_file)

    def _init_file(self):
        dir_name = os.path.dirname(os.path.abspath(self.filepath))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    async def send(self, payload: dict) -> bool:
        await asyncio.to_thread(self._write_payload, payload)
        return True

    def _write_payload(self, payload: dict):
        gateway_id = payload.get("gateway_id")
        file_exists = os.path.exists(self.filepath) and os.path.getsize(self.filepath) > 0
        data_list = payload.get("data", [])
        if not data_list:
            return
            
        telemetry_keys = set()
        env_keys = set()
        for msg in data_list:
            telemetry_keys.update(msg.get("telemetry", {}).keys())
            env_keys.update(msg.get("environment_state", {}).keys())
            
        sorted_telemetry_keys = sorted(list(telemetry_keys))
        sorted_env_keys = sorted(list(env_keys))
        
        header_fields = ["timestamp", "gateway_id", "device_id", "device_type", "environment_id"]
        header_fields += sorted_telemetry_keys
        header_fields += [f"env_{k}" for k in sorted_env_keys]
        
        if file_exists:
            try:
                with open(self.filepath, "r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    existing_headers = next(reader, None)
                    if existing_headers:
                        header_fields = existing_headers
            except Exception as e:
                logger.warning(f"CSVAdapter: Could not read existing header from '{self.filepath}': {e}. Using calculated header.")
                
        with open(self.filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header_fields, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
                
            for msg in data_list:
                row = {
                    "timestamp": msg.get("timestamp"),
                    "gateway_id": gateway_id,
                    "device_id": msg.get("device_id"),
                    "device_type": msg.get("device_type"),
                    "environment_id": msg.get("environment_id")
                }
                for k, v in msg.get("telemetry", {}).items():
                    row[k] = v
                for k, v in msg.get("environment_state", {}).items():
                    row[f"env_{k}"] = v
                writer.writerow(row)

    async def close(self):
        pass


class JSONLAdapter(BaseAdapter):
    def __init__(self, config: dict):
        self.config = config
        self.filepath = config.get("endpoint", "telemetry.jsonl")

    async def connect(self):
        await asyncio.to_thread(self._init_file)

    def _init_file(self):
        dir_name = os.path.dirname(os.path.abspath(self.filepath))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    async def send(self, payload: dict) -> bool:
        await asyncio.to_thread(self._write_payload, payload)
        return True

    def _write_payload(self, payload: dict):
        gateway_id = payload.get("gateway_id")
        gateway_name = payload.get("gateway_name")
        data_list = payload.get("data", [])
        if not data_list:
            return
            
        with open(self.filepath, "a", encoding="utf-8") as f:
            for msg in data_list:
                record = {
                    "timestamp": msg.get("timestamp"),
                    "gateway_id": gateway_id,
                    "gateway_name": gateway_name,
                    "device_id": msg.get("device_id"),
                    "device_type": msg.get("device_type"),
                    "environment_id": msg.get("environment_id"),
                    "telemetry": msg.get("telemetry"),
                    "environment_state": msg.get("environment_state")
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def close(self):
        pass


class SQLiteAdapter(BaseAdapter):
    def __init__(self, config: dict):
        self.config = config
        self.db_path = config.get("endpoint", "chora_telemetry.db")
        self.conn = None

    async def connect(self):
        await asyncio.to_thread(self._init_db)

    def _init_db(self):
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                gateway_id TEXT,
                device_id TEXT,
                device_type TEXT,
                metric TEXT,
                value REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS environment_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                environment_id TEXT,
                variable TEXT,
                value REAL
            )
        """)
        self.conn.commit()
        logger.info(f"SQLiteAdapter: Connected to database '{self.db_path}' and initialized tables.")

    async def send(self, payload: dict) -> bool:
        if not self.conn:
            raise RuntimeError("SQLite Adapter is not connected. Call connect() first.")
        await asyncio.to_thread(self._insert_payload, payload)
        return True

    def _insert_payload(self, payload: dict):
        gateway_id = payload.get("gateway_id")
        cursor = self.conn.cursor()
        
        for msg in payload.get("data", []):
            timestamp = msg.get("timestamp", time.time())
            device_id = msg.get("device_id")
            device_type = msg.get("device_type")
            telemetry = msg.get("telemetry", {})
            env_id = msg.get("environment_id")
            env_state = msg.get("environment_state", {})
            
            for metric, value in telemetry.items():
                try:
                    val_float = float(value)
                except (ValueError, TypeError):
                    val_float = None
                cursor.execute("""
                    INSERT INTO device_telemetry (timestamp, gateway_id, device_id, device_type, metric, value)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (timestamp, gateway_id, device_id, device_type, metric, val_float if val_float is not None else value))
                
            if env_id and env_state:
                for variable, value in env_state.items():
                    try:
                        val_float = float(value)
                    except (ValueError, TypeError):
                        val_float = None
                    cursor.execute("""
                        INSERT INTO environment_state (timestamp, environment_id, variable, value)
                        VALUES (?, ?, ?, ?)
                    """, (timestamp, env_id, variable, val_float if val_float is not None else value))
                    
        self.conn.commit()

    async def close(self):
        if self.conn:
            await asyncio.to_thread(self.conn.close)
            self.conn = None
            logger.info("SQLiteAdapter: Closed database connection.")


class ProtocolAdapterFactory:
    @staticmethod
    def create_adapter(config: dict) -> BaseAdapter:
        protocol = config.get("protocol", "mock").lower()
        if protocol == "http":
            return HTTPAdapter(config)
        elif protocol == "mqtt":
            return MQTTAdapter(config)
        elif protocol == "kafka":
            return KafkaAdapter(config)
        elif protocol == "csv":
            return CSVAdapter(config)
        elif protocol == "jsonl":
            return JSONLAdapter(config)
        elif protocol == "sqlite":
            return SQLiteAdapter(config)
        else:
            # Default mock adapter for backward compatibility / console logging
            class MockAdapter(BaseAdapter):
                async def connect(self):
                    pass
                async def send(self, payload: dict) -> bool:
                    # Print to terminal
                    print(f"\n======================================================================")
                    print(f"[MOCK BACKEND RECEIVED] Gateway: {payload['gateway_id']} ({payload['gateway_name']})")
                    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload['timestamp']))}")
                    print(f"Batch Size: {payload['batch_size']} metrics | Devices: {', '.join(payload['devices_reporting'])}")
                    for item in payload['data']:
                        metrics_str = ", ".join(f"{k}: {v:.3f}" if isinstance(v, float) else f"{k}: {v}" for k, v in item['telemetry'].items())
                        print(f"  |- Device: {item['device_id']} ({item['device_type']}) | Telemetry => {metrics_str}")
                    print(f"======================================================================\n")
                    return True
                async def close(self):
                    pass
            return MockAdapter()
