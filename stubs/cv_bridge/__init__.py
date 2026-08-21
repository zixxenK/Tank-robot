"""Minimal cv_bridge shim for image-node unit tests."""

import numpy as np

from sensor_msgs.msg import Image


class CvBridge:
    def imgmsg_to_cv2(self, message, desired_encoding="passthrough"):
        del desired_encoding
        if hasattr(message, "cv_image"):
            return message.cv_image.copy()
        height = int(getattr(message, "height", 0))
        width = int(getattr(message, "width", 0))
        if height <= 0 or width <= 0:
            raise ValueError("image dimensions are missing")
        channels = 1 if getattr(message, "encoding", "") in {"mono8", "8UC1"} else 3
        expected = height * width * channels
        data = np.frombuffer(getattr(message, "data", b""), dtype=np.uint8)
        if data.size < expected:
            raise ValueError("image data is shorter than its dimensions")
        return data[:expected].reshape((height, width, channels))

    def cv2_to_imgmsg(self, image, encoding="passthrough"):
        message = Image()
        message.height, message.width = image.shape[:2]
        message.encoding = encoding
        channels = image.shape[2] if image.ndim == 3 else 1
        message.step = message.width * channels
        message.data = image.tobytes()
        message.cv_image = image.copy()
        return message
