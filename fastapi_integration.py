from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import logging
import asyncio
import uvicorn
import threading

app = FastAPI()
bot_instance = None
active_websockets: list[WebSocket] = []

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Bot FastAPI</title>
    </head>
    <body>
        <h1>Bot is running</h1>
        <p>Connect to the WebSocket at /ws</p>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.get("/api/status")
async def get_status():
    if bot_instance and hasattr(bot_instance, 'get_initialization_status'):
        return bot_instance.get_initialization_status()
    return {"status": "Bot not fully initialized"}

async def broadcast_updates():
    while True:
        await asyncio.sleep(5) # Send updates every 5 seconds
        if active_websockets:
            try:
                message = {"status": "running", "timestamp": str(asyncio.get_event_loop().time())}
                # The `send_json` must be awaited
                await asyncio.gather(*[ws.send_json(message) for ws in active_websockets])
            except Exception as e:
                logging.debug(f"Could not broadcast to websocket: {e}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # You can define actions based on received data
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
        logging.info("WebSocket client disconnected")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)

def initialize_fastapi_with_bot(bot):
    global bot_instance
    bot_instance = bot

    def run_fastapi():
        uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")

    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_updates())
    except RuntimeError:
        pass

    return True

def stop_fastapi():
    logging.info("FastAPI server shutdown requested (manual stop required).")
