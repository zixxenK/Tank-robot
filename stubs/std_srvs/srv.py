class Trigger:
    class Request:
        pass

    class Response:
        def __init__(self):
            self.success = False
            self.message = ""


class SetBool:
    class Request:
        def __init__(self):
            self.data = False

    class Response:
        def __init__(self):
            self.success = False
            self.message = ""
