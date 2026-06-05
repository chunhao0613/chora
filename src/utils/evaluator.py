import math
import random
import logging

logger = logging.getLogger("SafeEvaluator")

class DictObject:
    """Wraps a dictionary to allow dot notation access while safe-guarding missing attributes."""
    def __init__(self, d: dict):
        self.__dict__.update(d or {})

    def __getattr__(self, name):
        # Fallback to 0.0 for safety to prevent system crashes on missing/misspelled variables
        logger.warning(f"Attribute '{name}' not found. Defaulting to 0.0.")
        return 0.0

class SafeEvaluator:
    @staticmethod
    def evaluate(expression: str, env_data: dict, specs: dict, state: dict, self_data: dict) -> float:
        """
        Safely evaluates mathematical expressions for device telemetry generation.
        """
        context = {
            'env': DictObject(env_data),
            'specs': DictObject(specs),
            'state': DictObject(state),
            'self': DictObject(self_data),
            # Math functions and constants
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'sinh': math.sinh,
            'cosh': math.cosh,
            'tanh': math.tanh,
            'exp': math.exp,
            'log': math.log,
            'log10': math.log10,
            'sqrt': math.sqrt,
            'pi': math.pi,
            'e': math.e,
            'min': min,
            'max': max,
            'abs': abs,
            # Random functions
            'random': random,
        }

        try:
            # We pass a clean globals dict without standard __builtins__ to prevent malicious code execution.
            # Only math/random features and topology objects are exposed.
            val = eval(expression, {"__builtins__": None}, context)
            return float(val)
        except Exception as e:
            logger.error(f"Error evaluating formula '{expression}': {e}. Returning 0.0.")
            return 0.0
