from fastapi import FastAPI
import time
from fastapi.middleware.cors import CORSMiddleware
from pymavkit import MAVDevice
from pymavkit.messages import VFRHUD, GlobalPosition, Heartbeat, BatteryStatus, GPSRaw, MAVState, Attitude, StatusText, MAVSeverity
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
    
msg_buffer = ""
def msg_cb(msg):
    global msg_buffer
    msg_buffer += msg.text + "\n"


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

@app.get("/telemetry")
def get_telemetry():
    global msg_id, heartbeat_id, vfr, global_pos, heartbeat, batt, gps, attitude, msg_buffer
    msg_to_send = msg_buffer
    msg_buffer = ""
    the_voltage = sum(batt.voltages[0:1]) / 1.0 / 1000
    return {"msg_id": msg_id, 
            "heading": vfr.heading_int * 1.0, 
            "airspeed": vfr.airspeed * 2.2376,
            "verticalSpeed": vfr.climbspeed * 2.2376,
            "horizontalSpeed": vfr.groundspeed * 2.2376,
            "altitudeASL": global_pos.alt_relative / 1000.0 * 3.281,
            "heartbeatID": heartbeat_id,
            "heartbeatHZ": calculate_hz(),
            "throttle": vfr.throttle,
            "voltages": [(voltage / 12500.0 if voltage / 12500.0 <= 1.1 else 0.0) for voltage in batt.voltages[0:6]],
            "voltage": float(the_voltage),
            "current": float(batt.current / 10.0),
            "power": float(batt.current / 10.0 * the_voltage),
            "soc": float(batt.soc),
            "time_left": "00:00",
            "wh_left": -1.0,
            "sats": int(gps.sats),
            "gps_fix": gps.fix_type.name,
            "armed": heartbeat.isArmed(),
            "estop": bool(heartbeat.state == MAVState.EMERGENCY),
            "mode": heartbeat.mode.name,
            "msg": msg_to_send,
            "lat": float(global_pos.lat / 10e6),
            "lon": float(global_pos.lon / 10e6),
            "roll": attitude.roll * 180.0 / 3.14,
            "pitch": attitude.pitch * 180.0 / 3.14
            }

@app.get("/")
def root():
    return {"message": "wassup"}
