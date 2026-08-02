class Trigger:
    class Request:
        pass

    class Response:
        def __init__(self):
            self.success = False
            self.message = ""
