from fastapi import FastAPI
import time
from fastapi.middleware.cors import CORSMiddleware
from pymavkit import MAVDevice
from pymavkit.messages import VFRHUD, GlobalPosition, Heartbeat, BatteryStatus
from pymavkit.protocols import HeartbeatProtocol

BUFFER_SIZE = 4
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


device = MAVDevice("udp:127.0.0.1:14550")

## protocols
hb_protocol = device.run_protocol(HeartbeatProtocol())

# listeners
vfr = device.add_listener(VFRHUD())
global_pos = device.add_listener(GlobalPosition())
heartbeat = device.add_listener(Heartbeat())
batt = device.add_listener(BatteryStatus())

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to your iPad's IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/telemetry")
def get_telemetry():
    global msg_id, heartbeat_id, vfr, global_pos, heartbeat, batt
    return {"msg_id": msg_id, 
            "heading": vfr.heading_int * 1.0, 
            "airspeed": vfr.airspeed,
            "verticalSpeed": vfr.climbspeed,
            "horizontalSpeed": vfr.groundspeed,
            "altitudeASL": global_pos.alt_relative / 1000.0,
            "heartbeatID": heartbeat_id,
            "heartbeatHZ": calculate_hz(),
            "throttle": vfr.throttle,
            }

@app.get("/")
def root():
    return {"message": "wassup"}
