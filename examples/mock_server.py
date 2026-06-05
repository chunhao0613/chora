import logging
import json
from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s'
)
logger = logging.getLogger("MockIoTServer")

async def handle_telemetry(request):
    try:
        # Verify Authorization header for JWT
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            # Print JWT token info
            logger.info(f"Request authorized using JWT: {token[:20]}... [length: {len(token)}]")
        else:
            logger.warning("Request did not contain a Bearer Token in Authorization header!")

        # Parse request body
        payload = await request.json()
        
        # Output clean console summary of received telemetry
        print(f"\n======================================================================")
        print(f"[MOCK SERVER] Received POST request at '/api/telemetry'")
        print(f"Gateway ID  : {payload.get('gateway_id')} ({payload.get('gateway_name')})")
        print(f"Batch Size  : {payload.get('batch_size')} packets | Devices: {', '.join(payload.get('devices_reporting', []))}")
        
        # Display telemetry details
        for item in payload.get('data', []):
            metrics_str = ", ".join(f"{k}: {v:.3f}" if isinstance(v, float) else f"{k}: {v}" for k, v in item.get('telemetry', {}).items())
            print(f"  |- Device: {item.get('device_id')} ({item.get('device_type')}) | Telemetry => {metrics_str}")
        print(f"======================================================================\n")
        
        return web.json_response({"status": "accepted", "records_processed": payload.get('batch_size')}, status=202)
        
    except Exception as e:
        logger.error(f"Failed to process request: {e}")
        return web.json_response({"status": "bad_request", "error": str(e)}, status=400)

if __name__ == '__main__':
    logger.info("Starting Mock Backend IoT Server on http://127.0.0.1:8080...")
    app = web.Application()
    app.router.add_post('/api/telemetry', handle_telemetry)
    web.run_app(app, host='127.0.0.1', port=8080)
