import asyncio
import time
import random
import logging
from collections import deque

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
        
        # Simulated connection status
        self.is_online = True
        
        self._running = False
        self._tasks = []

    async def start(self):
        """Starts the gateway loops: aggregation and network dispatching."""
        self._running = True
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
        """Simulates intermittent network dropouts based on configured reliability."""
        while self._running:
            # Check network reliability
            roll = random.random()
            new_status = roll < self.network_reliability
            
            if new_status != self.is_online:
                self.is_online = new_status
                if self.is_online:
                    logger.info(f"Gateway '{self.id}' [ONLINE] Connected to backend API.")
                    # Trigger a transmission immediately on reconnection
                    await self._attempt_transmission()
                else:
                    logger.warning(f"Gateway '{self.id}' [OFFLINE] Disconnected! Switching to local buffering.")
            
            # Check connection every 5 seconds
            await asyncio.sleep(5.0)

    async def _attempt_transmission(self):
        """Attempts to flush buffered telemetry payloads to the backend API."""
        if not self.is_online:
            return
            
        if not self.buffer:
            return
            
        logger.info(f"Gateway '{self.id}' [UPLOAD] Uploading {len(self.buffer)} buffered aggregate packet(s) to Backend API...")
        
        # Simulate network latency
        await asyncio.sleep(random.uniform(0.1, 0.4))
        
        # Flush all buffer entries (or batch up to limits if needed)
        uploaded_count = 0
        while self.buffer:
            payload = self.buffer[0] # peek
            
            # Mock upload execution
            success = self._mock_post_api(payload)
            if success:
                self.buffer.popleft() # remove from buffer
                uploaded_count += 1
            else:
                logger.error(f"Gateway '{self.id}' upload failed temporarily. Retrying later.")
                break
                
        if uploaded_count > 0:
            logger.info(f"Gateway '{self.id}' [SUCCESS] Successfully uploaded {uploaded_count} packet(s). Buffer size: {len(self.buffer)}")

    def _mock_post_api(self, payload: dict) -> bool:
        """Mocks HTTP POST to the backend system. Outputs payload metadata to console."""
        # Print a neat summary of the uploaded telemetry packet
        print(f"\n======================================================================")
        print(f"[BACKEND API RECEIVED] Gateway: {payload['gateway_id']} ({payload['gateway_name']})")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(payload['timestamp']))}")
        print(f"Batch Size: {payload['batch_size']} metrics | Devices: {', '.join(payload['devices_reporting'])}")
        
        # Show detailed telemetry inside the batch
        for item in payload['data']:
            metrics_str = ", ".join(f"{k}: {v:.3f}" if isinstance(v, float) else f"{k}: {v}" for k, v in item['telemetry'].items())
            print(f"  |- Device: {item['device_id']} ({item['device_type']}) | Telemetry => {metrics_str}")
        print(f"======================================================================\n")
        return True
