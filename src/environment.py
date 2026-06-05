import asyncio
import math
import random
import logging
import time

logger = logging.getLogger("Environment")

class PhysicsEnvironment:
    def __init__(self, config_data: dict):
        self.id = config_data["id"]
        self.name = config_data["name"]
        self.update_interval = config_data.get("update_interval_sec", 1.0)
        self.state_configs = config_data.get("state_variables", {})
        
        # Initialize environmental states
        self.state = {}
        self.elapsed_time = 0.0
        self._initialize_states()
        self._running = False
        self._task = None

    def _initialize_states(self):
        """Pre-populate initial states for environments."""
        for var_name, conf in self.state_configs.items():
            t = conf["type"]
            if t == "constant":
                self.state[var_name] = conf["value"]
            elif t == "random_walk":
                self.state[var_name] = conf.get("initial", 0.0)
            elif t in ["sine_wave", "diurnal"]:
                self.state[var_name] = conf.get("bias", 0.0)
            else:
                self.state[var_name] = 0.0

    def get_state(self) -> dict:
        """Returns a copy of the current environment state."""
        return dict(self.state)

    async def start(self):
        """Starts the physical simulation loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Environment '{self.name}' ({self.id}) started physics engine.")

    async def stop(self):
        """Stops the physics loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Environment '{self.name}' ({self.id}) stopped physics engine.")

    async def _run_loop(self):
        while self._running:
            try:
                self._update_physics()
                await asyncio.sleep(self.update_interval)
                self.elapsed_time += self.update_interval
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in physics engine of env '{self.id}': {e}")
                await asyncio.sleep(1.0)

    def _update_physics(self):
        """Computes the next time step physical updates for all configured variables."""
        for var_name, conf in self.state_configs.items():
            t = conf["type"]
            if t == "constant":
                # Constants do not change
                continue
                
            elif t == "sine_wave":
                amp = conf.get("amplitude", 1.0)
                period = conf.get("period_sec", 60.0)
                bias = conf.get("bias", 0.0)
                noise_lvl = conf.get("noise", 0.0)
                
                # Sine wave equation: bias + amplitude * sin(2 * pi * t / T) + noise
                val = bias + amp * math.sin(2 * math.pi * self.elapsed_time / period)
                if noise_lvl > 0:
                    val += random.uniform(-noise_lvl, noise_lvl)
                self.state[var_name] = val
                
            elif t == "diurnal":
                # Diurnal cycle (e.g. sunlight) is modeled by half-wave rectified sine
                max_val = conf.get("max_val", 1000.0)
                period = conf.get("period_sec", 60.0)
                
                val = max_val * math.sin(2 * math.pi * self.elapsed_time / period)
                self.state[var_name] = max(0.0, val) # Solar radiation cannot be negative
                
            elif t == "random_walk":
                min_val = conf.get("min_val", 0.0)
                max_val = conf.get("max_val", 100.0)
                step = conf.get("step", 1.0)
                current = self.state.get(var_name, conf.get("initial", 0.0))
                
                # Random walk: step randomly between [-step, step]
                new_val = current + random.uniform(-step, step)
                self.state[var_name] = max(min_val, min(max_val, new_val))
                
            else:
                logger.warning(f"Unknown generator type '{t}' for variable '{var_name}' in env '{self.id}'")
