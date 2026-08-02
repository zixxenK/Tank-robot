class QoSReliabilityPolicy:
    RELIABLE = 1
    BEST_EFFORT = 2


class QoSDurabilityPolicy:
    VOLATILE = 1
    TRANSIENT_LOCAL = 2


class QoSProfile:
    def __init__(self, depth, reliability=None, durability=None):
        self.depth = depth
        self.reliability = reliability
        self.durability = durability
