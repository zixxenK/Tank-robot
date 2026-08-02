class LaunchConfiguration:
    def __init__(self, name, default=None):
        self.name = name
        self.default = default

    def perform(self, context):
        if isinstance(context, dict):
            return str(context.get(self.name, self.default or ""))
        return str(self.default or "")


class EnvironmentVariable:
    def __init__(self, name, default_value=None):
        self.name = name
        self.default_value = default_value


class PathJoinSubstitution:
    def __init__(self, substitutions=None):
        self.substitutions = substitutions if substitutions is not None else []


class PythonExpression:
    def __init__(self, expression):
        self.expression = expression
