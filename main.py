from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import time
from fastapi.middleware.cors import CORSMiddleware
from pymavkit import MAVDevice
from pymavkit.messages import VFRHUD, GlobalPosition, Heartbeat, BatteryStatus, GPSRaw, MAVState, Attitude, StatusText, MAVSeverity
from pymavkit.protocols import HeartbeatProtocol
from pydantic import BaseModel
import asyncio

BUFFER_SIZE = 5
heartbeat_timestamps = []
msg_id = 0
heartbeat_id = 0

def heartbeat_cb(mavMsg):
    global heartbeat_timestamps, BUFFER_SIZE, heartbeat_id
    heartbeat_id += 1
    heartbeat_timestamps.insert(0, mavMsg.timestamp / 1000.0)
    if len(heartbeat_timestamps) > BUFFER_SIZE:
        heartbeat_timestamps.pop()

def calculate_avg(l: list) -> float:
    Sum = 0.0
    for i in range(len(l) - 1):
        Sum += l[i] - l[i + 1]
    return Sum / (len(l) - 1)

def calculate_hz() -> float:
    global heartbeat_timestamps
    if len(heartbeat_timestamps) > 1:
        avg = calculate_avg(heartbeat_timestamps)
        if avg < time.time() - heartbeat_timestamps[0]:
            avg = calculate_avg([time.time(), *heartbeat_timestamps])
        return 1.0 / avg
    else:
        return -1.0
    
msg_buffer = ""
def msg_cb(msg):
    global msg_buffer
    msg_buffer += msg.text + "\n"

class ModeBody(BaseModel):
    mode: str

websocket_connections: list[WebSocket] = []


device = MAVDevice("udp:127.0.0.1:14550")

## protocols
hb_protocol = device.run_protocol(HeartbeatProtocol())

# listeners
vfr = VFRHUD()
global_pos = GlobalPosition()
heartbeat = Heartbeat(heartbeat_cb)
batt = BatteryStatus()
gps = GPSRaw()
attitude = Attitude()
status_text = StatusText("", MAVSeverity.INFO, msg_cb)
device.add_listener(vfr)
device.add_listener(global_pos)
device.add_listener(heartbeat)
device.add_listener(batt)
device.add_listener(gps)
device.add_listener(attitude)
device.add_listener(status_text)

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to your iPad's IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/mode")
def set_mode(body: ModeBody) -> dict:
    return {"ok": True, "mode": "RTL"}


@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket):
    await ws.accept()
    websocket_connections.append(ws)

def get_state() -> dict:
    global msg_id, heartbeat_id, vfr, global_pos, heartbeat, batt, gps, attitude, msg_buffer
    msg_to_send = msg_buffer
    msg_buffer = ""
    return {'timestamp': time.time() * 1000.0,
            'batterySoc': 92.0,
            'armed': False,
            'estopOn': True,
            'mode': "RTL",
            'currentLat': 37.7749,
            'currentLon': -122.4194,
            'heading': 45.0,
            'altitude': 120.0,
            'throttle': 30.0,
            'speed': 12.0,
            'roll': 5.0,
            'pitch': -2.0,
            'heartbeat': "1 hz",
            'status': "Status #0",
            }

@app.get("/")
def root():
    return {"message": "wassup"}

async def broadcast() -> None:
        if not websocket_connections:
            return
        payload = get_state()
        # Send to all; drop dead sockets
        dead: list[WebSocket] = []
        for ws in websocket_connections:
            try:
                await ws.send_json(payload)
            except WebSocketDisconnect:
                dead.append(ws)
            except Exception:
                dead.append(ws)
        for ws in dead:
            websocket_connections.remove(ws)


async def main_loop():
    while True:
        await broadcast()
        await asyncio.sleep(1.0)

asyncio.run(main_loop())
