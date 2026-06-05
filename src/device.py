import asyncio
import time
import logging
from src.utils.evaluator import SafeEvaluator

logger = logging.getLogger("Device")

class EdgeDevice:
    def __init__(self, config_data: dict, environment, gateway):
        self.id = config_data["id"]
        self.name = config_data["name"]
        self.type = config_data["type"]
        self.update_interval = config_data.get("update_interval_sec", 1.0)
        self.specs = config_data.get("specs", {})
        self.telemetry_rules = config_data.get("telemetry_rules", {})
        
        # Initial mutable internal state
        self.state = config_data.get("initial_state", {}).copy()
        
        # External bounds
        self.environment = environment
        self.gateway = gateway
        
        self._running = False
        self._task = None

    async def start(self):
        """Starts the device data-sampling loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Device '{self.name}' ({self.id}) started telemetry loop.")

    async def stop(self):
        """Stops the device loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Device '{self.name}' ({self.id}) stopped telemetry loop.")

    async def _run_loop(self):
        while self._running:
            try:
                await self._generate_and_send_telemetry()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in telemetry loop of device '{self.id}': {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _generate_and_send_telemetry(self):
        """Samples the physical environment, evaluates formulas, updates state, and sends to gateway."""
        # 1. Sample environment
        env_data = self.environment.get_state()
        
        # 2. Evaluate rules sequentially
        telemetry = {}
        for key, formula in self.telemetry_rules.items():
            val = SafeEvaluator.evaluate(
                expression=formula,
                env_data=env_data,
                specs=self.specs,
                state=self.state,
                self_data=telemetry
            )
            telemetry[key] = val
            
            # If the calculated telemetry matches a state variable, update the mutable state
            if key in self.state:
                self.state[key] = val

        # 3. Create telemetry message
        message = {
            "device_id": self.id,
            "device_type": self.type,
            "timestamp": time.time(),
            "telemetry": telemetry,
            "environment_id": self.environment.id,
            "environment_state": env_data
        }

        # 4. Dispatch to Gateway
        await self.gateway.receive_telemetry(message)
