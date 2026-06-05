import asyncio
import argparse
import json
import logging
import os
import sys
import time
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class ChaosEventRequest(BaseModel):
    event: str = Field(..., description="Name of the chaos event, e.g. 'typhoon'")
    duration_sec: float = Field(30.0, description="Duration of the event in seconds")

class EnvironmentRequest(BaseModel):
    id: str = Field(..., description="Unique ID of the environment")
    name: str = Field(..., description="Human-readable name of the environment")
    update_interval_sec: float = Field(..., description="Physics engine tick interval in seconds")
    state_variables: Dict[str, Any] = Field(..., description="Configuration of state variables")

class DeviceRequest(BaseModel):
    id: str = Field(..., description="Unique ID of the device")
    name: str = Field(..., description="Human-readable name of the device")
    type: str = Field(..., description="Type of the device")
    environment_id: str = Field(..., description="ID of the environment to bind to")
    gateway_id: str = Field(..., description="ID of the gateway to bind to")
    update_interval_sec: float = Field(..., description="Telemetry generation interval in seconds")
    specs: Dict[str, Any] = Field(default_factory=dict, description="Static specifications/constants for formulas")
    telemetry_rules: Dict[str, str] = Field(..., description="Mathematical formulas for telemetry fields")
    initial_state: Dict[str, Any] = Field(default_factory=dict, description="Initial values for device states")

from src.environment import PhysicsEnvironment
from src.gateway import EdgeGateway
from src.device import EdgeDevice

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SimulationManager")

class SimulationRunner:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.environments = {}
        self.gateways = {}
        self.devices = {}
        self.api_runner = None
        self.output_override = None
        self.observer = None
        self.loop = None

    def load_topology(self, output_override: str = None):
        """Loads and parses the topology configuration JSON."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        if output_override is not None:
            self.output_override = output_override

        logger.info(f"Loading topology configuration from '{self.config_path}'...")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        dev_mode = config.get("dev_mode", False)

        # 1. Instantiate Environments
        for env_conf in config.get("environments", []):
            env = PhysicsEnvironment(env_conf)
            self.environments[env.id] = env

        # 2. Instantiate Gateways
        for gw_conf in config.get("gateways", []):
            gw_conf["dev_mode"] = dev_mode
            if self.output_override:
                ext = os.path.splitext(self.output_override)[1].lower()
                if ext == ".csv":
                    gw_conf["connection"] = {"protocol": "csv", "endpoint": self.output_override}
                elif ext == ".jsonl":
                    gw_conf["connection"] = {"protocol": "jsonl", "endpoint": self.output_override}
                elif ext in [".db", ".sqlite", ".sqlite3"]:
                    gw_conf["connection"] = {"protocol": "sqlite", "endpoint": self.output_override}
                else:
                    gw_conf["connection"] = {"protocol": "jsonl", "endpoint": self.output_override}
            gw = EdgeGateway(gw_conf)
            self.gateways[gw.id] = gw

        # 3. Instantiate Devices and bind them to Environment and Gateway
        for dev_conf in config.get("devices", []):
            env_id = dev_conf["environment_id"]
            gw_id = dev_conf["gateway_id"]

            env = self.environments.get(env_id)
            gw = self.gateways.get(gw_id)

            if not env:
                raise ValueError(f"Device '{dev_conf['id']}' refers to undefined environment '{env_id}'")
            if not gw:
                raise ValueError(f"Device '{dev_conf['id']}' refers to undefined gateway '{gw_id}'")

            device = EdgeDevice(dev_conf, env, gw)
            self.devices[device.id] = device

        logger.info(
            f"Successfully initialized topology:\n"
            f"  - Environments: {len(self.environments)} ({', '.join(self.environments.keys())})\n"
            f"  - Gateways: {len(self.gateways)} ({', '.join(self.gateways.keys())})\n"
            f"  - Devices: {len(self.devices)} ({', '.join(self.devices.keys())})"
        )

    async def start(self):
        """Starts all concurrent loops and the HTTP Control Plane Server."""
        logger.info("Starting simulation subsystems...")
        
        # Start environments first so physical values are available
        for env in self.environments.values():
            await env.start()

        # Start gateways to listen for incoming telemetry
        for gw in self.gateways.values():
            await gw.start()

        # Start devices to begin sampling and telemetry transmission
        for device in self.devices.values():
            await device.start()

        # Start the Control Plane HTTP API server
        await self._start_api_server()

        # Start the config watcher
        self.loop = asyncio.get_running_loop()
        self._start_config_watcher()

        logger.info("All subsystems are running asynchronously.")

    async def stop(self):
        """Stops all running subsystems gracefully, including the API server."""
        logger.info("Stopping simulation subsystems...")
        
        # Stop config watcher
        self._stop_config_watcher()

        # Stop Control Plane HTTP API server
        await self._stop_api_server()

        # Stop devices first to stop generating new telemetry
        for device in self.devices.values():
            await device.stop()

        # Stop gateways to finish processing and flushing buffered items
        for gw in self.gateways.values():
            await gw.stop()

        # Stop environments
        for env in self.environments.values():
            await env.stop()

        logger.info("Simulation subsystems stopped.")

    async def _start_api_server(self):
        """Initializes and runs the Control Plane HTTP server for chaos engineering."""
        logger.info("Starting Control Plane API Server on http://127.0.0.1:8081...")
        from fastapi import FastAPI, HTTPException
        import uvicorn

        app = FastAPI(
            title="Chora IoT Edge Simulation Engine",
            description="Dynamic control plane APIs for environment/device registration and chaos engineering.",
            version="2.0.0"
        )

        @app.post("/api/env/{env_id}/event", tags=["Chaos Engineering"])
        async def inject_chaos_event(env_id: str, body: ChaosEventRequest):
            """Endpoint to dynamically inject a chaos event override into an environment's physics engine."""
            env = self.environments.get(env_id)
            if not env:
                raise HTTPException(status_code=404, detail=f"Environment '{env_id}' not found")
            env.trigger_chaos_event(body.event, body.duration_sec)
            return {
                "status": "success",
                "message": f"Chaos event '{body.event}' successfully injected into environment '{env_id}' for {body.duration_sec}s"
            }

        @app.post("/api/topology/environment", status_code=201, tags=["Topology Management"])
        async def add_environment(body: EnvironmentRequest):
            """Endpoint to dynamically instantiate a new PhysicsEnvironment in the running system."""
            if body.id in self.environments:
                raise HTTPException(status_code=409, detail=f"Environment '{body.id}' already exists")
            try:
                env_dict = body.model_dump()
                env = PhysicsEnvironment(env_dict)
                await env.start()
                self.environments[env.id] = env
                logger.info(f"Dynamically added and started Environment '{env.name}' ({env.id})")
                return {"status": "success", "message": f"Environment '{body.id}' created and started successfully"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to instantiate environment: {e}")

        @app.post("/api/topology/device", status_code=201, tags=["Topology Management"])
        async def add_device(body: DeviceRequest):
            """Endpoint to dynamically instantiate a new EdgeDevice and bind it to an env and gateway."""
            if body.id in self.devices:
                raise HTTPException(status_code=409, detail=f"Device '{body.id}' already exists")
            
            env = self.environments.get(body.environment_id)
            gw = self.gateways.get(body.gateway_id)
            
            if not env:
                raise HTTPException(status_code=404, detail=f"Referenced Environment '{body.environment_id}' not found")
            if not gw:
                raise HTTPException(status_code=404, detail=f"Referenced Gateway '{body.gateway_id}' not found")
                
            try:
                dev_dict = body.model_dump()
                device = EdgeDevice(dev_dict, env, gw)
                await device.start()
                self.devices[device.id] = device
                logger.info(f"Dynamically added and started Device '{device.name}' ({device.id})")
                return {"status": "success", "message": f"Device '{body.id}' created and started successfully"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to instantiate device: {e}")

        @app.get("/api/topology/status", tags=["Topology Management"])
        async def get_topology_status():
            """Endpoint to view the current topology definition and telemetry states in memory."""
            envs_status = []
            for env in self.environments.values():
                envs_status.append({
                    "id": env.id,
                    "name": env.name,
                    "active_event": env.active_event,
                    "elapsed_time": env.elapsed_time,
                    "state": env.get_state()
                })
                
            gws_status = []
            for gw in self.gateways.values():
                gws_status.append({
                    "id": gw.id,
                    "name": gw.name,
                    "is_online": gw.is_online,
                    "buffer_size": gw.buffer_size,
                    "current_buffer_len": len(gw.buffer)
                })
                
            devs_status = []
            for dev in self.devices.values():
                devs_status.append({
                    "id": dev.id,
                    "name": dev.name,
                    "type": dev.type,
                    "update_interval_sec": dev.update_interval,
                    "environment_id": dev.environment.id,
                    "gateway_id": dev.gateway.id,
                    "state": dev.state
                })
                
            return {
                "environments": envs_status,
                "gateways": gws_status,
                "devices": devs_status
            }

        config = uvicorn.Config(app, host="0.0.0.0", port=8081, log_level="warning")
        self.api_server = uvicorn.Server(config)
        self.api_task = asyncio.create_task(self.api_server.serve())
        logger.info("Control Plane API Server started successfully on port 8081 (accessible externally).")

    async def _stop_api_server(self):
        """Shuts down the Control Plane HTTP server."""
        if hasattr(self, 'api_server') and self.api_server:
            logger.info("Stopping Control Plane API Server...")
            self.api_server.should_exit = True
            await self.api_task
            self.api_server = None
            logger.info("Control Plane API Server stopped.")

    def _start_config_watcher(self):
        config_dir = os.path.dirname(os.path.abspath(self.config_path))
        if not config_dir:
            config_dir = "."
        
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class ConfigChangeHandler(FileSystemEventHandler):
            def __init__(self, runner):
                self.runner = runner
                self.config_path_abs = os.path.abspath(runner.config_path)
                self.last_reload = 0.0

            def on_modified(self, event):
                if os.path.abspath(event.src_path) == self.config_path_abs:
                    now = time.time()
                    if now - self.last_reload > 0.5:
                        self.last_reload = now
                        logger.info(f"Detected change in configuration file '{self.runner.config_path}'")
                        asyncio.run_coroutine_threadsafe(self.runner.reload_topology(), self.runner.loop)

        self.config_handler = ConfigChangeHandler(self)
        self.observer = Observer()
        self.observer.schedule(self.config_handler, path=config_dir, recursive=False)
        self.observer.start()
        logger.info(f"Started monitoring config folder '{config_dir}' for changes.")

    def _stop_config_watcher(self):
        if self.observer:
            logger.info("Stopping configuration file monitor...")
            self.observer.stop()
            self.observer.join()
            self.observer = None

    async def stop_simulation(self):
        """Stops device, gateway, and environment simulation loops without stopping the API server."""
        for device in self.devices.values():
            await device.stop()
        for gw in self.gateways.values():
            await gw.stop()
        for env in self.environments.values():
            await env.stop()
        self.devices.clear()
        self.gateways.clear()
        self.environments.clear()

    async def reload_topology(self):
        logger.info("Configuration change detected! Reloading topology...")
        try:
            await self.stop_simulation()
            self.load_topology(output_override=self.output_override)
            for env in self.environments.values():
                await env.start()
            for gw in self.gateways.values():
                await gw.start()
            for device in self.devices.values():
                await device.start()
            logger.info("Topology successfully reloaded and restarted.")
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")

async def main():
    parser = argparse.ArgumentParser(description="High-Fidelity IoT Edge Simulation System Daemon")
    parser.add_argument(
        "--config", 
        type=str, 
        default="config/topology_config.json", 
        help="Path to the topology JSON configuration file"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional local output path to save telemetry directly (supports .csv, .jsonl, .db/.sqlite)"
    )
    args = parser.parse_args()

    runner = SimulationRunner(args.config)
    try:
        runner.load_topology(output_override=args.output)
    except Exception as e:
        logger.critical(f"Failed to load topology: {e}")
        sys.exit(1)

    await runner.start()

    logger.info("Running simulation indefinitely as a Daemon. Press Ctrl+C or send SIGTERM to terminate.")
    try:
        # Keep running until cancelled
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await runner.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Simulation terminated by user via KeyboardInterrupt.")
