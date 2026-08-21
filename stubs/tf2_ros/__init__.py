class TransformBroadcaster:
    def __init__(self, node=None):
        self.node = node
        self.transforms = []

    def sendTransform(self, transform):
        self.transforms.append(transform)
