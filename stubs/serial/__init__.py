class SerialException(Exception):
    pass


class Serial:
    def __init__(
        self,
        port=None,
        baudrate=115200,
        timeout=0.1,
        write_timeout=None,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.is_open = True
        self.in_waiting = 0
        self._read_buffer = bytearray()
        self.writes = []

    def write(self, data):
        payload = bytes(data) if data is not None else b""
        self.writes.append(payload)
        return len(payload)

    def readline(self):
        if not self._read_buffer:
            return b""
        try:
            end = self._read_buffer.index(ord("\n")) + 1
        except ValueError:
            end = len(self._read_buffer)
        result = bytes(self._read_buffer[:end])
        del self._read_buffer[:end]
        self.in_waiting = len(self._read_buffer)
        return result

    def read(self, size=1):
        size = max(0, int(size))
        result = bytes(self._read_buffer[:size])
        del self._read_buffer[:size]
        self.in_waiting = len(self._read_buffer)
        return result

    def inject(self, data):
        self._read_buffer.extend(bytes(data))
        self.in_waiting = len(self._read_buffer)

    def reset_input_buffer(self):
        self._read_buffer.clear()
        self.in_waiting = 0

    def flush(self):
        return None

    def close(self):
        self.is_open = False
