import socket
import struct
import threading
import queue
import time

TCP_IP = '192.168.4.1'
TCP_PORT = 8080
GPIO_MASK = 0x0FFF  # 12-bit mask
VREF = 5.3

def convert(data):
    return ((((data & GPIO_MASK) - 2048) / 4096) * (2 * VREF))

class TCPWaveformReader:
    def __init__(self, frame_size, max_queue=10, retry_interval=2):
        self.frame_size = frame_size
        self.queue = queue.Queue(maxsize=max_queue)
        self._stop_event = threading.Event()
        self.sock = None
        self._connected = False
        self.retry_interval = retry_interval
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
            except Exception as e:
                print(f"TCP connect failed: {e}. Retrying in {self.retry_interval}s...")
                time.sleep(self.retry_interval)

    def _reader_thread(self):
        while not self._stop_event.is_set():
            if not self._connected or self.sock is None:
                self._connect()
                continue
            try:
                raw_bytes = self._recv_exact(self.frame_size * 2)
                if raw_bytes is not None and len(raw_bytes) == self.frame_size * 2:
                    samples = [
                        convert(val)
                        for val in struct.unpack('>' + 'H' * self.frame_size, raw_bytes)
                    ]
                    try:
                        self.queue.put(samples, timeout=0.1)
                    except queue.Full:
                        pass
                else:
                    # Connection lost, reset and retry
                    self._connected = False
                    if self.sock:
                        try:
                            self.sock.close()
                        except Exception:
                            pass
                        self.sock = None
            except Exception:
                self._connected = False
                if self.sock:
                    try:
                        self.sock.close()
                    except Exception:
                        pass
                    self.sock = None
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
