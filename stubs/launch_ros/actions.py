class Node:
    def __init__(
        self,
        package=None,
        executable=None,
        name=None,
        parameters=None,
        arguments=None,
        output=None,
        condition=None,
        **kwargs,
    ):
        self.package = package
        self.executable = executable
        self.name = name
        self.parameters = parameters if parameters is not None else []
        self.arguments = arguments if arguments is not None else []
        self.output = output
        self.condition = condition
        self.extra = kwargs
