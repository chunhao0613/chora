import asyncio
import math
import random
import logging

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

        # Chaos event state
        self.active_event = None
        self.event_expires_at = 0.0

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
            elif t == "markov_chain":
                states = conf.get("states", [])
                self.state[var_name] = conf.get("initial", states[0] if states else "sunny")
            else:
                self.state[var_name] = 0.0

    def get_state(self) -> dict:
        """Returns a copy of the current environment state."""
        return dict(self.state)

    def trigger_chaos_event(self, event_name: str, duration_sec: float):
        """Triggers a chaos event that temporarily overrides environmental variables."""
        self.active_event = event_name.lower()
        self.event_expires_at = self.elapsed_time + duration_sec
        logger.warning(f"Environment '{self.id}': Chaos event '{event_name}' triggered for {duration_sec} seconds.")

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
                
            elif t == "markov_chain":
                states = conf.get("states", [])
                transition_matrix = conf.get("transition_matrix", {})
                current = self.state.get(var_name, conf.get("initial"))
                if not current and states:
                    current = states[0]
                if current in transition_matrix:
                    probs = transition_matrix[current]
                    choices = list(probs.keys())
                    weights = [float(w) for w in probs.values()]
                    if choices and weights:
                        new_val = random.choices(choices, weights=weights)[0]
                        self.state[var_name] = new_val
            else:
                logger.warning(f"Unknown generator type '{t}' for variable '{var_name}' in env '{self.id}'")

        # Apply chaos event overrides
        if self.active_event:
            if self.elapsed_time < self.event_expires_at:
                self._apply_chaos_overrides()
            else:
                logger.info(f"Environment '{self.id}': Chaos event '{self.active_event}' expired. Returning to normal physics.")
                self.active_event = None

    def _apply_chaos_overrides(self):
        """Overwrites state variables based on active chaos event settings."""
        if self.active_event == "typhoon":
            if "wind_speed" in self.state:
                self.state["wind_speed"] = 75.0 + random.uniform(0.0, 15.0)
            if "cloud_cover" in self.state:
                self.state["cloud_cover"] = 1.0
            if "base_temp" in self.state:
                self.state["base_temp"] = max(5.0, self.state["base_temp"] - 6.0)
                
        elif self.active_event == "heatwave":
            if "base_temp" in self.state:
                self.state["base_temp"] = self.state["base_temp"] + 15.0
            if "cloud_cover" in self.state:
                self.state["cloud_cover"] = 0.0
                
        elif self.active_event == "eclipse":
            if "solar_radiation" in self.state:
                self.state["solar_radiation"] = 0.0
