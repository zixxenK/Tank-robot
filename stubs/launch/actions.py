class DeclareLaunchArgument:
    def __init__(self, name, default_value=None, description=""):
        self.name = name
        self.default_value = default_value
        self.description = description


class ExecuteProcess:
    def __init__(self, cmd=None, output=None, shell=False, condition=None):
        self.cmd = cmd
        self.output = output
        self.shell = shell
        self.condition = condition


class LogInfo:
    def __init__(self, msg=None):
        self.msg = msg


class OpaqueFunction:
    def __init__(self, function=None):
        self.function = function


class IncludeLaunchDescription:
    def __init__(self, launch_description_source=None, launch_arguments=None):
        self.launch_description_source = launch_description_source
        self.launch_arguments = launch_arguments
