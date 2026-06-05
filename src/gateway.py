import asyncio
import time
import random
import logging
from collections import deque
from src.adapters import ProtocolAdapterFactory

logger = logging.getLogger("Gateway")

class EdgeGateway:
    def __init__(self, config_data: dict):
        self.id = config_data["id"]
        self.name = config_data["name"]
        self.buffer_size = config_data.get("buffer_size", 100)
        self.aggregation_interval = config_data.get("aggregation_interval_sec", 2.0)
        self.network_reliability = config_data.get("network_reliability", 0.9)
        
        # In-memory buffer for offline storage (FIFO queue)
        self.buffer = deque(maxlen=self.buffer_size)
        # Queue for incoming telemetry from edge devices
        self.telemetry_queue = asyncio.Queue()
        
        # Instantiate real connection adapter based on connection config
        self.connection_config = config_data.get("connection", {})
        self.connection_config["dev_mode"] = config_data.get("dev_mode", False)
        self.adapter = ProtocolAdapterFactory.create_adapter(self.connection_config)
        
        # Simulated connection status
        self.is_online = True
        
        self._running = False
        self._tasks = []

    async def start(self):
        """Starts the gateway loops: aggregation and network dispatching."""
        self._running = True
        
        # Attempt initial adapter connection
        try:
            logger.info(f"Gateway '{self.id}' connecting protocol adapter...")
            await self.adapter.connect()
            self.is_online = True
            logger.info(f"Gateway '{self.id}' initial adapter connection established.")
        except Exception as e:
            logger.error(f"Gateway '{self.id}' initial connection failed: {e}. Starting in offline buffering mode.")
            self.is_online = False
            
        self._tasks.append(asyncio.create_task(self._run_aggregation_loop()))
        self._tasks.append(asyncio.create_task(self._run_network_simulation_loop()))
        logger.info(f"Gateway '{self.name}' ({self.id}) started.")

    async def stop(self):
        """Stops the gateway processes."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        
        # Close connection adapter
        try:
            await self.adapter.close()
        except Exception as e:
            logger.error(f"Error closing adapter for Gateway '{self.id}': {e}")
            
        logger.info(f"Gateway '{self.name}' ({self.id}) stopped.")

    async def receive_telemetry(self, message: dict):
        """Called by devices to send raw telemetry into the gateway's queue."""
        await self.telemetry_queue.put(message)

    async def _run_aggregation_loop(self):
        """Periodically aggregates telemetry from the queue and buffers/sends them."""
        while self._running:
            try:
                await asyncio.sleep(self.aggregation_interval)
                
                # Drain the queue of any messages received
                batch = []
                while not self.telemetry_queue.empty():
                    batch.append(self.telemetry_queue.get_nowait())
                
                if not batch:
                    continue
                
                # Perform basic protocol conversion & aggregation
                aggregated_payload = {
                    "gateway_id": self.id,
                    "gateway_name": self.name,
                    "timestamp": time.time(),
                    "batch_size": len(batch),
                    "devices_reporting": list(set(d["device_id"] for d in batch)),
                    "data": batch
                }
                
                # Append to buffer
                if len(self.buffer) >= self.buffer_size:
                    logger.warning(f"Gateway '{self.id}' buffer FULL (max {self.buffer_size}). Evicting oldest packet.")
                self.buffer.append(aggregated_payload)
                
                # Try to transmit buffered data
                await self._attempt_transmission()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in aggregation loop of gateway '{self.id}': {e}", exc_info=True)

    async def _run_network_simulation_loop(self):
        """Simulates intermittent network dropouts and manages adapter reconnection."""
        while self._running:
            # Check network reliability
            roll = random.random()
            simulated_online = roll < self.network_reliability
            
            if simulated_online != self.is_online:
                if simulated_online:
                    logger.info(f"Gateway '{self.id}' network simulation: RESTORING connection.")
                    try:
                        await self.adapter.connect()
                        self.is_online = True
                        logger.info(f"Gateway '{self.id}' [ONLINE] Reconnected successfully.")
                        # Trigger an immediate upload of cached packets
                        await self._attempt_transmission()
                    except Exception as e:
                        logger.error(f"Gateway '{self.id}' adapter reconnection failed: {e}. Remaining offline.")
                        self.is_online = False
                else:
                    logger.warning(f"Gateway '{self.id}' [OFFLINE] Network dropout simulated! Closing connection.")
                    self.is_online = False
                    try:
                        await self.adapter.close()
                    except Exception:
                        pass
            
            # Check connection every 5 seconds
            await asyncio.sleep(5.0)

    async def _attempt_transmission(self):
        """Attempts to flush buffered telemetry payloads to the backend system."""
        if not self.is_online:
            return
            
        if not self.buffer:
            return
            
        # Flush all buffer entries
        uploaded_count = 0
        while self.buffer:
            payload = self.buffer[0] # peek
            
            try:
                # Transmit using adapter
                success = await self.adapter.send(payload)
                if success:
                    self.buffer.popleft() # remove from buffer
                    uploaded_count += 1
                else:
                    logger.error(f"Gateway '{self.id}' upload refused by endpoint. Buffering data.")
                    break
            except Exception as e:
                logger.error(f"Gateway '{self.id}' transmission error: {e}. Switching to offline buffer mode.")
                self.is_online = False
                try:
                    await self.adapter.close()
                except Exception:
                    pass
                break
                
        if uploaded_count > 0:
            logger.debug(f"Gateway '{self.id}' [SUCCESS] Successfully uploaded {uploaded_count} packet(s). Buffer size: {len(self.buffer)}")
