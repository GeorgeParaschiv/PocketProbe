import socket
import struct
import threading
import queue
import time
import subprocess
import os

TCP_IP = '192.168.4.1'
TCP_PORT = 8080
GPIO_MASK = 0x0FFF  # 12-bit mask
VREF = 1.5

WIFI_OPTIONS = [
    ("PocketProbe", "starlight123"),
    ("PocketProbe2", "starlight123"),
]
WIFI_SSID = WIFI_OPTIONS[0][0]
WIFI_PASSWORD = WIFI_OPTIONS[0][1]

def convert(data):
    """Convert raw ADC data to a normalized value (before gain/offset processing)"""
    raw = data & GPIO_MASK

    # Reverse bit order (12 bits)
    reversed_val = int(f'{raw:012b}'[::-1], 2)

    # Convert from 12-bit two's complement to signed
    if reversed_val >= 2048:
        signed_val = reversed_val - 4096
    else:
        signed_val = reversed_val

    # Return normalized ADC voltage (just VREF scaling, no gain/offset)
    return (signed_val / 2048.0) * VREF


class TCPWaveformReader:
    def __init__(self, frame_size, max_queue=10, retry_interval=1):
        self.frame_size = frame_size
        self.queue = queue.Queue(maxsize=max_queue)
        self._stop_event = threading.Event()
        self.sock = None
        self._connected = False
        self._was_ever_connected = False
        self.retry_interval = retry_interval
        self.battery_info = None
        self._wifi_connecting = False
        self._wifi_result = None  # (success: bool, message: str) or None
        self._wifi_ssid = WIFI_SSID
        self._wifi_password = WIFI_PASSWORD
        self._user_disconnected = True
        self._wifi_succeeded = False
        self._tcp_retries = 0
        self._thread = threading.Thread(target=self._readerThread, daemon=True)
        self._thread.start()

    def connectWifi(self, ssid=None, password=None):
        """Start WiFi connection to ESP32 AP in a background thread."""
        if self._wifi_connecting:
            return
        if ssid is not None:
            self._wifi_ssid = ssid
        if password is not None:
            self._wifi_password = password
        self._user_disconnected = False
        self._wifi_succeeded = False
        self._tcp_retries = 0
        self._wifi_connecting = True
        self._wifi_result = None
        t = threading.Thread(target=self._wifiConnectThread, daemon=True)
        t.start()

    def userDisconnect(self):
        """Disconnect and stop auto-reconnect until connectWifi is called again."""
        self._user_disconnected = True
        self._wifi_succeeded = False
        self._disconnect("Disconnected by user")

    def getWifiResult(self):
        """Poll for WiFi connection result. Returns (success, message) or None if still in progress."""
        result = self._wifi_result
        if result is not None:
            self._wifi_result = None
        return result

    @property
    def wifiConnecting(self):
        return self._wifi_connecting

    @property
    def connected(self):
        return self._connected

    @property
    def autoConnecting(self):
        """True when WiFi succeeded and TCP is still trying to connect."""
        return self._wifi_succeeded and not self._connected

    def _wifiConnectThread(self):
        try:
            subprocess.run(
                ["netsh", "wlan", "disconnect"],
                capture_output=True, text=True, timeout=10
            )
            time.sleep(1)

            self._ensureWifiProfile()

            result = subprocess.run(
                ["netsh", "wlan", "connect", f"name={self._wifi_ssid}",
                 f"ssid={self._wifi_ssid}"],
                capture_output=True, text=True, timeout=15
            )
            print(f"netsh connect stdout: {result.stdout.strip()}")
            print(f"netsh connect stderr: {result.stderr.strip()}")

            if "successfully" in result.stdout.lower():
                time.sleep(2)
                self._wifi_succeeded = True
                self._wifi_result = (True, "WiFi connected")
            else:
                self._user_disconnected = True
                self._wifi_result = (False, "WiFi failed — is device on?")
        except subprocess.TimeoutExpired:
            self._user_disconnected = True
            self._wifi_result = (False, "WiFi timed out")
        except Exception as e:
            self._user_disconnected = True
            self._wifi_result = (False, str(e))
        finally:
            self._wifi_connecting = False

    def _ensureWifiProfile(self):
        check = subprocess.run(
            ["netsh", "wlan", "show", "profile", self._wifi_ssid],
            capture_output=True, text=True, timeout=10
        )
        if self._wifi_ssid in check.stdout:
            return

        profile_xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{self._wifi_ssid}</name>
    <SSIDConfig><SSID><name>{self._wifi_ssid}</name></SSID></SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>manual</connectionMode>
    <MSM><security>
        <authEncryption><authentication>WPA2PSK</authentication>
            <encryption>AES</encryption><useOneX>false</useOneX></authEncryption>
        <sharedKey><keyType>passPhrase</keyType>
            <protected>false</protected><keyMaterial>{self._wifi_password}</keyMaterial></sharedKey>
    </security></MSM>
</WLANProfile>"""
        tmp = os.path.join(os.environ.get("TEMP", "."), "esp_ap_profile.xml")
        with open(tmp, "w") as f:
            f.write(profile_xml)

        result = subprocess.run(
            ["netsh", "wlan", "add", "profile", f"filename={tmp}"],
            capture_output=True, text=True, timeout=10
        )
        out = result.stdout.strip()
        print(f"netsh add profile: {out}")

        if "denied" in out.lower() or "used" not in out.lower():
            print("Profile add may need admin — retrying elevated")
            try:
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", "netsh",
                    f'wlan add profile filename="{tmp}"', None, 0
                )
                time.sleep(3)
            except Exception as e:
                print(f"Elevated profile add failed: {e}")

        try:
            os.remove(tmp)
        except OSError:
            pass

    MAX_TCP_RETRIES = 2

    def _connect(self):
        while not self._stop_event.is_set() and not self._connected:
            if self._user_disconnected:
                time.sleep(self.retry_interval)
                return
            if self._tcp_retries >= self.MAX_TCP_RETRIES:
                print("TCP failed — WiFi may be down")
                self._wifi_succeeded = False
                self._user_disconnected = True
                self._tcp_retries = 0
                return
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((TCP_IP, TCP_PORT))
                sock.settimeout(2)
                self.sock = sock
                self._connected = True
                self._tcp_retries = 0
                print("TCP Connected")
                self._was_ever_connected = True
            except Exception:
                self._tcp_retries += 1
                time.sleep(self.retry_interval)

    def _disconnect(self, msg="TCP Lost, Reconnecting..."):
        if self._connected:
            print(msg)
        self._connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _readerThread(self):
        while not self._stop_event.is_set():
            if not self._connected or self.sock is None:
                self._connect()
                continue
            try:
                header = self._recvExact(2)
                if header is None or len(header) != 2:
                    self._disconnect()
                    continue

                msg_len = struct.unpack('>H', header)[0]

                if msg_len == self.frame_size * 2:
                    raw_bytes = self._recvExact(msg_len)
                    if raw_bytes is not None and len(raw_bytes) == msg_len:
                        samples = [
                            convert(val)
                            for val in struct.unpack('>' + 'H' * self.frame_size, raw_bytes)
                        ]
                        try:
                            self.queue.put(samples, timeout=0.1)
                        except queue.Full:
                            pass
                    else:
                        self._disconnect()

                elif msg_len == 2:
                    batt_bytes = self._recvExact(2)
                    if batt_bytes is not None and len(batt_bytes) == 2:
                        status = batt_bytes[0]
                        percentage = batt_bytes[1]
                        self.battery_info = {
                            'charging': status == 1,
                            'percentage': percentage
                        }
                    else:
                        self._disconnect()

                else:
                    print(f"Unknown message length: {msg_len}, skipping")
                    skip = self._recvExact(msg_len)
                    if skip is None:
                        self._disconnect()

            except Exception:
                self._disconnect()
                time.sleep(self.retry_interval)

    MAX_RECV_TIMEOUTS = 2

    def _recvExact(self, n):
        buf = b''
        timeouts = 0
        while len(buf) < n and self._connected and self.sock:
            try:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    return None
                buf += chunk
                timeouts = 0
            except socket.timeout:
                timeouts += 1
                if timeouts >= self.MAX_RECV_TIMEOUTS:
                    return None
                continue
            except Exception:
                return None
        return buf if len(buf) == n else None

    def getLatestSamples(self):
        """Return the oldest frame in the queue, or None if none available."""
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None

    def sendPacket(self, pkt):
        if self._connected and self.sock:
            try:
                self.sock.sendall(pkt)
            except Exception:
                self._connected = False

    def close(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1)
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self._connected = False
