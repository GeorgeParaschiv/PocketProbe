import serial
import struct
import threading
import queue

# --- Configuration ---
COM_PORT = 'COM3'
BAUD_RATE = 115200
BYTES_TO_READ = 2000  # 1000 samples * 2 bytes per uint16_t

GPIO_MASK = 0x0FFF  # 12-bit mask
VREF = 5.3

def convert(data):
    return ((float((data & GPIO_MASK) - 2048) / 4096) * (2 * VREF))

class SerialWaveformReader:
    def __init__(self, frame_size, port='COM3', baud=115200, max_queue=60):
        self.ser = serial.Serial(port, baud, timeout=None)
        self.frame_size = frame_size
        self.queue = queue.Queue(maxsize=max_queue)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._reader_thread, daemon=True)
        self._thread.start()

    def _reader_thread(self):
        while not self._stop_event.is_set():
            # Wait for start-of-frame marker 'S'
            try:
                while True:
                    marker = self.ser.read(1)
                    if marker == b'S':
                        break
                    if self._stop_event.is_set():
                        return
                samples = []
                for _ in range(self.frame_size):
                    data = self.ser.read(2)
                    sample = struct.unpack('<H', data)[0]
                    samples.append(convert(sample))
                    
                if len(samples) == self.frame_size:
                    try:
                        self.queue.put(samples, timeout=0.1)
                    except queue.Full:
                        pass
            except Exception:
                pass

    def get_latest_samples(self):
        """Return the oldest frame in the queue, or None if none available."""
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1)
        self.ser.close()