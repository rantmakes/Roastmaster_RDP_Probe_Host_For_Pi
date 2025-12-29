import time
import socket
import struct
import json
import os
import board
import busio
import digitalio
import adafruit_mcp9600

# ==============================================================================
# ============================== CONFIGURATION =================================
# ==============================================================================

# Network Configuration
HOST_SERIAL = "My Probe Host"
SERVER_PORT = 5050
MULTICAST_GROUP = '224.0.0.1'

# Timers (in seconds)
SYNC_SEND_RATE = 2.0
TEMP_SEND_RATE = 1.0

# Status LED Pin (Optional)
STATUS_LED_PIN = board.D2
STATUS_LED_ACTIVE_LOW = True 

# I2C Configuration
# I2C uses fixed pins on the Pi: GPIO 2 (SDA) and GPIO 3 (SCL).
# No manual pin definition needed for I2C initialization in CircuitPython.

# ==============================================================================
# ============================ RDP PROTOCOL CONSTANTS ==========================
# ==============================================================================

RDP_VERSION_1_0 = "RDP_1.0"
KEY_VERSION = "RPVersion"
KEY_SERIAL = "RPSerial"
KEY_EPOCH = "RPEpoch"
KEY_PAYLOAD = "RPPayload"
KEY_EVENT_TYPE = "RPEventType"
KEY_CHANNEL = "RPChannel"
KEY_VALUE = "RPValue"

EVENT_SYN = 1
EVENT_ACK = 2
EVENT_TEMP = 3

# ==============================================================================
# ============================ CLASSES & LOGIC =================================
# ==============================================================================

class HostState:
    SEARCHING = 0
    CONNECTED = 1

class ProbeHost:
    def __init__(self):
        self.state = HostState.SEARCHING
        self.send_count = 0 
        self.server_address = None
        self.last_sync_time = 0
        self.last_temp_time = 0
        
        # Initialize LED
        self.led = None
        if STATUS_LED_PIN:
            self.led = digitalio.DigitalInOut(STATUS_LED_PIN)
            self.led.direction = digitalio.Direction.OUTPUT
            self.set_led(False)

        # Initialize UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
        self.sock.bind(('', SERVER_PORT))
        self.sock.setblocking(False)

        # Initialize Sensor (MCP9600) via I2C
        self.probes = []
        try:
            # Initialize I2C bus (SCL=GPIO3, SDA=GPIO2)
            i2c = board.I2C() 
            
            # Initialize MCP9600
            # Default address is 0x67. Change address=0x66 etc if you bridged pads.
            mcp = adafruit_mcp9600.MCP9600(i2c)
            
            # Optional: Set thermocouple type (Default is K)
            # mcp.thermocouple_type = "K" 

            self.probes.append({
                "channel": 1, 
                "handle": mcp,
                "temp": None,
                "error": False
            })
            print(f"Initialized MCP9600 Probe on Channel 1 (I2C)")
            
        except ValueError as e:
            print(f"I2C Error: {e}")
            print("Did you enable I2C in raspi-config?")
        except Exception as e:
            print(f"Error initializing Sensor: {e}")

    def set_led(self, on):
        if not self.led: return
        if STATUS_LED_ACTIVE_LOW:
            self.led.value = not on
        else:
            self.led.value = on

    def blink_led(self, times, duration=0.1):
        if not self.led: return
        for _ in range(times):
            self.set_led(True)
            time.sleep(duration)
            self.set_led(False)
            time.sleep(duration)

    def write_web_log(self, datagram):
        """Writes current packet to JSON for the Apache web monitor"""
        file_path = "/var/www/html/rdp_packet.json"
        
        # Add a local timestamp for the web display
        # We copy the dict to avoid modifying the one sent over UDP
        log_data = datagram.copy()
        log_data['LocalTimestamp'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        
        try:
            temp_path = file_path + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(log_data, f)
            os.replace(temp_path, file_path)
        except Exception as e:
            # Silent fail to avoid spamming console if web folder permission is wrong
            pass

    def read_incoming(self):
        try:
            data, addr = self.sock.recvfrom(1024)
            message = data.decode('utf-8')
            try:
                packet = json.loads(message)
            except json.JSONDecodeError:
                return 

            if (packet.get(KEY_VERSION) == RDP_VERSION_1_0 and 
                packet.get(KEY_SERIAL) == HOST_SERIAL and 
                packet.get(KEY_EVENT_TYPE) == str(EVENT_ACK)):
                
                print(f"Received ACK from Server at {addr[0]}")
                self.server_address = (addr[0], SERVER_PORT)
                self.state = HostState.CONNECTED
                self.last_temp_time = 0
                
        except BlockingIOError:
            pass 

    def send_syn(self):
        payload_array = [{ KEY_EVENT_TYPE: EVENT_SYN }]
        
        datagram = {
            KEY_VERSION: RDP_VERSION_1_0,
            KEY_SERIAL: HOST_SERIAL,
            KEY_EPOCH: self.send_count,
            KEY_PAYLOAD: json.dumps(payload_array)
        }
        
        msg_bytes = json.dumps(datagram).encode('utf-8')
        
        print(f"Sending SYN to {MULTICAST_GROUP}:{SERVER_PORT}")
        
        # Write to web log
        self.write_web_log(datagram)
        
        self.sock.sendto(msg_bytes, (MULTICAST_GROUP, SERVER_PORT))
        self.send_count += 1
        self.blink_led(2)

    def read_probes(self):
        for p in self.probes:
            try:
                # MCP9600 reading
                temp_c = p["handle"].temperature
                p["temp"] = temp_c
                p["error"] = False
            except Exception as e:
                print(f"Probe Error on Ch {p['channel']}: {e}")
                p["temp"] = None
                p["error"] = True
                self.blink_led(5, 0.05)

    def send_temps(self):
        self.set_led(True)
        self.read_probes()
        
        payload_list = []
        for p in self.probes:
            if not p["error"] or True: 
                val_str = "null"
                if p["temp"] is not None:
                    val_str = "{:.2f}".format(p["temp"])
                
                event = {
                    KEY_EVENT_TYPE: EVENT_TEMP,
                    KEY_CHANNEL: p["channel"],
                    KEY_VALUE: val_str
                }
                payload_list.append(event)

        if not payload_list:
            self.set_led(False)
            return

        datagram = {
            KEY_VERSION: RDP_VERSION_1_0,
            KEY_SERIAL: HOST_SERIAL,
            KEY_EPOCH: self.send_count,
            KEY_PAYLOAD: json.dumps(payload_list) 
        }

        msg_bytes = json.dumps(datagram).encode('utf-8')

        # Write to web log
        self.write_web_log(datagram)

        if self.server_address:
            self.sock.sendto(msg_bytes, self.server_address)
            self.send_count += 1
        
        self.set_led(False)

    def run(self):
        print(f"Roastmaster RDP Host Started (MCP9600 I2C). Serial: {HOST_SERIAL}")
        
        while True:
            current_time = time.monotonic()
            self.read_incoming()

            if self.state == HostState.SEARCHING:
                if current_time - self.last_sync_time > SYNC_SEND_RATE:
                    self.send_syn()
                    self.last_sync_time = current_time
            
            elif self.state == HostState.CONNECTED:
                if current_time - self.last_temp_time > TEMP_SEND_RATE:
                    self.send_temps()
                    self.last_temp_time = current_time
            
            time.sleep(0.01)

# ==============================================================================
# ================================= MAIN =======================================
# ==============================================================================

if __name__ == "__main__":
    host = ProbeHost()
    try:
        host.run()
    except KeyboardInterrupt:
        print("\nStopping Roastmaster Host...")
