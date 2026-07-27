class KeyValue:
    def __init__(self, key="", value=""):
        self.key = key
        self.value = value


class DiagnosticStatus:
    OK = 0
    WARN = 1
    ERROR = 2
    STALE = 3

    def __init__(self):
        self.name = ""
        self.hardware_id = ""
        self.level = DiagnosticStatus.OK
        self.message = ""
        self.values = []


class _Header:
    def __init__(self):
        self.stamp = None


class DiagnosticArray:
    def __init__(self):
        self.header = _Header()
        self.status = []
