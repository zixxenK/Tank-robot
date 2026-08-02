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

    def write(self, data):
        return len(data) if data is not None else 0

    def readline(self):
        return b""

    def close(self):
        self.is_open = False
