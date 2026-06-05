import asyncio
import argparse
import json
import logging
import os
import sys

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

    def load_topology(self):
        """Loads and parses the topology configuration JSON."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        logger.info(f"Loading topology configuration from '{self.config_path}'...")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # 1. Instantiate Environments
        for env_conf in config.get("environments", []):
            env = PhysicsEnvironment(env_conf)
            self.environments[env.id] = env

        # 2. Instantiate Gateways
        for gw_conf in config.get("gateways", []):
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
        """Starts all concurrent loops."""
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

        logger.info("All subsystems are running asynchronously.")

    async def stop(self):
        """Stops all running subsystems gracefully."""
        logger.info("Stopping simulation subsystems...")
        
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

async def main():
    parser = argparse.ArgumentParser(description="High-Fidelity IoT Edge Simulation System")
    parser.add_argument(
        "--config", 
        type=str, 
        default="config/topology_config.json", 
        help="Path to the topology JSON configuration file"
    )
    parser.add_argument(
        "--duration", 
        type=int, 
        default=30, 
        help="Simulation duration in seconds (0 for infinite)"
    )
    args = parser.parse_args()

    runner = SimulationRunner(args.config)
    try:
        runner.load_topology()
    except Exception as e:
        logger.critical(f"Failed to load topology: {e}")
        sys.exit(1)

    await runner.start()

    if args.duration > 0:
        logger.info(f"Running simulation for {args.duration} seconds...")
        await asyncio.sleep(args.duration)
        await runner.stop()
    else:
        logger.info("Running simulation indefinitely. Press Ctrl+C to terminate.")
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await runner.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Simulation terminated by user via KeyboardInterrupt.")
