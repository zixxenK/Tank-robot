class Bool:
    def __init__(self):
        self.data = False

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