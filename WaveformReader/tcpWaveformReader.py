import socket
import struct
import threading
import queue
import time

TCP_IP = '192.168.4.1'
TCP_PORT = 8080
GPIO_MASK = 0x0FFF  # 12-bit mask
VREF = 1.5

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
    def __init__(self, frame_size, max_queue=10, retry_interval=2):
        self.frame_size = frame_size
        self.queue = queue.Queue(maxsize=max_queue)
        self._stop_event = threading.Event()
        self.sock = None
        self._connected = False
        self._was_ever_connected = False
        self.retry_interval = retry_interval
        self.battery_info = None  # {'charging': bool, 'percentage': int} or None
        self._thread = threading.Thread(target=self._reader_thread, daemon=True)
        self._thread.start()

    def _connect(self):
        while not self._stop_event.is_set() and not self._connected:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((TCP_IP, TCP_PORT))
                self.sock = sock
                self._connected = True
                print("TCP connection established.")
                self._was_ever_connected = True
            except Exception as e:
                if not self._was_ever_connected:
                    # First time trying to connect, don't spam
                    pass
                time.sleep(self.retry_interval)

    def _disconnect(self, msg="TCP connection lost. Reconnecting..."):
        """Helper to cleanly handle disconnection"""
        if self._connected:
            print(msg)
        self._connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _reader_thread(self):
        while not self._stop_event.is_set():
            if not self._connected or self.sock is None:
                self._connect()
                continue
            try:
                # Read 2-byte length header (big-endian)
                header = self._recv_exact(2)
                if header is None or len(header) != 2:
                    self._disconnect()
                    continue

                msg_len = struct.unpack('>H', header)[0]

                if msg_len == self.frame_size * 2:
                    # Frame data
                    raw_bytes = self._recv_exact(msg_len)
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
                    # Battery status packet: [status, percentage]
                    batt_bytes = self._recv_exact(2)
                    if batt_bytes is not None and len(batt_bytes) == 2:
                        status = batt_bytes[0]    # 0 = on battery, 1 = charging
                        percentage = batt_bytes[1] # 0-100
                        self.battery_info = {
                            'charging': status == 1,
                            'percentage': percentage
                        }
                    else:
                        self._disconnect()

                else:
                    # Unknown message length — try to skip
                    print(f"Unknown message length: {msg_len}, skipping")
                    skip = self._recv_exact(msg_len)
                    if skip is None:
                        self._disconnect()

            except Exception:
                self._disconnect()
                time.sleep(self.retry_interval)

    def _recv_exact(self, n):
        buf = b''
        while len(buf) < n and self._connected and self.sock:
            try:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    return None
                buf += chunk
            except Exception:
                return None
        return buf if len(buf) == n else None

    def get_latest_samples(self):
        """Return the oldest frame in the queue, or None if none available."""
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None

    def send_packet(self, pkt):
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
