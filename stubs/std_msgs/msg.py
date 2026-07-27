class Bool:
    def __init__(self, data=False):
        self.data = data


class Empty:
    pass


class Float32:
    def __init__(self):
        self.data = 0.0


class UInt16:
    def __init__(self):
        self.data = 0


class Header:
    def __init__(self):
        self.stamp = None
        self.frame_id = ""


class Int32MultiArray:
    def __init__(self, data=None):
        self.data = data if data is not None else []
