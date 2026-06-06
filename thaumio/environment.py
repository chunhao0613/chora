import asyncio
import math
import random
import logging

logger = logging.getLogger("Environment")

ENV_PRESETS = {
    "smart_farm": {
        "temperature": {
            "type": "sine_wave",
            "amplitude": 8.0,
            "period_sec": 30.0,
            "bias": 24.0,
            "noise": 0.2
        },
        "solar_radiation": {
            "type": "diurnal",
            "max_val": 800.0,
            "period_sec": 60.0
        },
        "cloud_cover": {
            "type": "random_walk",
            "min_val": 0.0,
            "max_val": 1.0,
            "step": 0.05,
            "initial": 0.2
        },
        "weather_state": {
            "type": "markov_chain",
            "states": ["sunny", "cloudy", "rainy"],
            "initial": "sunny",
            "transition_matrix": {
                "sunny": {"sunny": 0.7, "cloudy": 0.25, "rainy": 0.05},
                "cloudy": {"sunny": 0.3, "cloudy": 0.5, "rainy": 0.2},
                "rainy": {"sunny": 0.1, "cloudy": 0.4, "rainy": 0.5}
            }
        }
    },
    "server_room": {
        "ambient_temp": {
            "type": "sine_wave",
            "amplitude": 2.0,
            "period_sec": 120.0,
            "bias": 21.0,
            "noise": 0.1
        },
        "humidity": {
            "type": "random_walk",
            "min_val": 35.0,
            "max_val": 65.0,
            "step": 0.5,
            "initial": 50.0
        },
        "ac_load": {
            "type": "sine_wave",
            "amplitude": 15.0,
            "period_sec": 60.0,
            "bias": 45.0,
            "noise": 0.5
        }
    },
    "electric_vehicle": {
        "speed": {
            "type": "random_walk",
            "min_val": 0.0,
            "max_val": 120.0,
            "step": 5.0,
            "initial": 50.0
        },
        "battery_temp": {
            "type": "sine_wave",
            "amplitude": 5.0,
            "period_sec": 180.0,
            "bias": 35.0,
            "noise": 0.2
        },
        "motor_rpm": {
            "type": "constant",
            "value": 3200.0
        }
    }
}

class PhysicsEnvironment:
    def __init__(self, config_data: dict):
        self.id = config_data["id"]
        self.name = config_data["name"]
        self.update_interval = config_data.get("update_interval_sec", 1.0)
        self.preset = config_data.get("preset")
        
        preset_configs = ENV_PRESETS.get(self.preset, {}) if self.preset else {}
        self.state_configs = {**preset_configs, **config_data.get("state_variables", {})}
        
        # Initialize environmental states
        self.base_state = {}
        self.state = {}
        self.elapsed_time = 0.0
        self._initialize_states()
        self._running = False
        self._task = None

        # Chaos event state
        self.chaos_events = config_data.get("chaos_events", {})
        self.active_event = None
        self.event_expires_at = 0.0
        self.active_event_overrides = None
        
        self.default_chaos_events = {
            "typhoon": {
                "overrides": {
                    "wind_speed": "75.0 + random.uniform(0.0, 15.0)",
                    "cloud_cover": "1.0",
                    "base_temp": "max(5.0, env.base_temp - 6.0)"
                }
            },
            "heatwave": {
                "overrides": {
                    "base_temp": "env.base_temp + 15.0",
                    "cloud_cover": "0.0"
                }
            },
            "eclipse": {
                "overrides": {
                    "solar_radiation": "0.0"
                }
            }
        }

    def _initialize_states(self):
        """Pre-populate initial states for environments."""
        for var_name, conf in self.state_configs.items():
            t = conf["type"]
            if t == "constant":
                self.base_state[var_name] = conf["value"]
            elif t == "random_walk":
                self.base_state[var_name] = conf.get("initial", 0.0)
            elif t in ["sine_wave", "diurnal"]:
                self.base_state[var_name] = conf.get("bias", 0.0)
            elif t == "markov_chain":
                states = conf.get("states", [])
                self.base_state[var_name] = conf.get("initial", states[0] if states else "sunny")
            else:
                self.base_state[var_name] = 0.0
        self.state = dict(self.base_state)

    def get_state(self) -> dict:
        """Returns a copy of the current environment state."""
        return dict(self.state)

    def trigger_chaos_event(self, event_name: str, duration_sec: float, overrides: dict = None):
        """Triggers a chaos event that temporarily overrides environmental variables."""
        self.active_event = event_name.lower()
        self.event_expires_at = self.elapsed_time + duration_sec
        
        # Priority: dynamic post overrides > config-defined overrides > fallback presets
        if overrides:
            self.active_event_overrides = overrides
        elif self.active_event in self.chaos_events:
            self.active_event_overrides = self.chaos_events[self.active_event].get("overrides", {})
        elif self.active_event in self.default_chaos_events:
            self.active_event_overrides = self.default_chaos_events[self.active_event].get("overrides", {})
        else:
            self.active_event_overrides = {}
            
        logger.warning(
            f"Environment '{self.id}': Chaos event '{event_name}' triggered for {duration_sec} seconds. "
            f"Active Overrides: {self.active_event_overrides}"
        )

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
                # Constants do not change in base_state
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
                self.base_state[var_name] = val
                
            elif t == "diurnal":
                # Diurnal cycle (e.g. sunlight) is modeled by half-wave rectified sine
                max_val = conf.get("max_val", 1000.0)
                period = conf.get("period_sec", 60.0)
                
                val = max_val * math.sin(2 * math.pi * self.elapsed_time / period)
                self.base_state[var_name] = max(0.0, val) # Solar radiation cannot be negative
                
            elif t == "random_walk":
                min_val = conf.get("min_val", 0.0)
                max_val = conf.get("max_val", 100.0)
                step = conf.get("step", 1.0)
                current = self.base_state.get(var_name, conf.get("initial", 0.0))
                
                # Random walk: step randomly between [-step, step]
                new_val = current + random.uniform(-step, step)
                self.base_state[var_name] = max(min_val, min(max_val, new_val))
                
            elif t == "markov_chain":
                states = conf.get("states", [])
                transition_matrix = conf.get("transition_matrix", {})
                current = self.base_state.get(var_name, conf.get("initial"))
                if not current and states:
                    current = states[0]
                if current in transition_matrix:
                    probs = transition_matrix[current]
                    choices = list(probs.keys())
                    weights = [float(w) for w in probs.values()]
                    if choices and weights:
                        new_val = random.choices(choices, weights=weights)[0]
                        self.base_state[var_name] = new_val
            else:
                logger.warning(f"Unknown generator type '{t}' for variable '{var_name}' in env '{self.id}'")

        # Sync current state to base_state
        self.state = dict(self.base_state)

        # Apply chaos event overrides
        if self.active_event:
            if self.elapsed_time < self.event_expires_at:
                self._apply_chaos_overrides()
            else:
                logger.info(f"Environment '{self.id}': Chaos event '{self.active_event}' expired. Returning to normal physics.")
                self.active_event = None

    def _apply_chaos_overrides(self):
        """Overwrites state variables based on active chaos event settings."""
        if not self.active_event_overrides:
            return
            
        from thaumio.utils.evaluator import SafeEvaluator
        
        pre_override_state = dict(self.state)
        for var_name, formula in self.active_event_overrides.items():
            if var_name in self.state:
                val = SafeEvaluator.evaluate(
                    expression=str(formula),
                    env_data=pre_override_state,
                    specs={},
                    state={},
                    self_data={}
                )
                self.state[var_name] = val
