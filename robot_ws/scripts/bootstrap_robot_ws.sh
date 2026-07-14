#!/usr/bin/env bash
set -euo pipefail

# Rock64 Ranger ROS 2 workspace bootstrap
WS_ROOT="${1:-$HOME/robot_ws}"
SRC_DIR="$WS_ROOT/src"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ERROR: ros2 CLI not found in PATH. Source your ROS 2 environment first."
  echo "Example: source /opt/ros/jazzy/setup.bash"
  exit 1
fi

mkdir -p "$SRC_DIR"
cd "$SRC_DIR"

create_pkg_if_missing() {
  local pkg="$1"
  shift
  if [ ! -d "$pkg" ]; then
    ros2 pkg create --build-type ament_python "$pkg" "$@"
  else
    echo "Package '$pkg' already exists. Reusing existing folder."
  fi
}

create_pkg_if_missing robot_drivers --dependencies rclpy geometry_msgs std_msgs sensor_msgs
create_pkg_if_missing robot_teleop --dependencies rclpy geometry_msgs sensor_msgs
create_pkg_if_missing robot_bringup --dependencies launch launch_ros rclpy

mkdir -p robot_drivers/include
mkdir -p robot_drivers/robot_drivers
mkdir -p robot_teleop/robot_teleop
mkdir -p robot_bringup/launch robot_bringup/config robot_bringup/robot_bringup

python3 - <<'PY'
from pathlib import Path
import textwrap

ws = Path.cwd()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


# robot_drivers nodes
write(
    ws / "robot_drivers" / "robot_drivers" / "__init__.py",
    """
    """,
)

write(
    ws / "robot_drivers" / "robot_drivers" / "stm32_bridge.py",
    """
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist


    class Stm32Bridge(Node):
        def __init__(self) -> None:
            super().__init__("stm32_bridge")
            self.declare_parameter("serial_port", "/dev/ttyACM0")
            self.declare_parameter("baudrate", 115200)
            self._sub = self.create_subscription(Twist, "/cmd_vel", self._on_cmd_vel, 20)
            self.get_logger().info("stm32_bridge started")

        def _on_cmd_vel(self, msg: Twist) -> None:
            self.get_logger().debug(
                f"cmd_vel linear.x={msg.linear.x:.3f}, angular.z={msg.angular.z:.3f}"
            )


    def main(args=None) -> None:
        rclpy.init(args=args)
        node = Stm32Bridge()
        try:
            rclpy.spin(node)
        finally:
            node.destroy_node()
            rclpy.shutdown()
    """,
)

write(
    ws / "robot_drivers" / "robot_drivers" / "esp32_bridge.py",
    """
    import rclpy
    from rclpy.node import Node


    class Esp32Bridge(Node):
        def __init__(self) -> None:
            super().__init__("esp32_bridge")
            self.declare_parameter("camera_url", "http://esp32cam.local/stream")
            self.get_logger().info("esp32_bridge started")


    def main(args=None) -> None:
        rclpy.init(args=args)
        node = Esp32Bridge()
        try:
            rclpy.spin(node)
        finally:
            node.destroy_node()
            rclpy.shutdown()
    """,
)

write(
    ws / "robot_drivers" / "setup.py",
    """
    from setuptools import find_packages, setup

    package_name = "robot_drivers"

    setup(
        name=package_name,
        version="0.0.1",
        packages=find_packages(exclude=["test"]),
        data_files=[
            (
                "share/ament_index/resource_index/packages",
                [f"resource/{package_name}"],
            ),
            (f"share/{package_name}", ["package.xml"]),
        ],
        install_requires=["setuptools"],
        zip_safe=True,
        maintainer="Rock64 Ranger Team",
        maintainer_email="todo@example.com",
        description="Hardware abstraction and bridge nodes.",
        license="MIT",
        tests_require=["pytest"],
        entry_points={
            "console_scripts": [
                "stm32_bridge = robot_drivers.stm32_bridge:main",
                "esp32_bridge = robot_drivers.esp32_bridge:main",
            ],
        },
    )
    """,
)


# robot_teleop node
write(
    ws / "robot_teleop" / "robot_teleop" / "__init__.py",
    """
    """,
)

write(
    ws / "robot_teleop" / "robot_teleop" / "ps5_bridge.py",
    """
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist


    class Ps5Bridge(Node):
        def __init__(self) -> None:
            super().__init__("ps5_bridge")
            self._pub = self.create_publisher(Twist, "/cmd_vel", 20)
            self.declare_parameter("deadzone", 0.08)
            self.get_logger().info("ps5_bridge started")


    def main(args=None) -> None:
        rclpy.init(args=args)
        node = Ps5Bridge()
        try:
            rclpy.spin(node)
        finally:
            node.destroy_node()
            rclpy.shutdown()
    """,
)

write(
    ws / "robot_teleop" / "setup.py",
    """
    from setuptools import find_packages, setup

    package_name = "robot_teleop"

    setup(
        name=package_name,
        version="0.0.1",
        packages=find_packages(exclude=["test"]),
        data_files=[
            (
                "share/ament_index/resource_index/packages",
                [f"resource/{package_name}"],
            ),
            (f"share/{package_name}", ["package.xml"]),
        ],
        install_requires=["setuptools"],
        zip_safe=True,
        maintainer="Rock64 Ranger Team",
        maintainer_email="todo@example.com",
        description="Teleoperation and input bridge nodes.",
        license="MIT",
        tests_require=["pytest"],
        entry_points={
            "console_scripts": [
                "ps5_bridge = robot_teleop.ps5_bridge:main",
            ],
        },
    )
    """,
)


# robot_bringup launch + setup
write(
    ws / "robot_bringup" / "robot_bringup" / "__init__.py",
    """
    """,
)

write(
    ws / "robot_bringup" / "launch" / "robot_system.launch.py",
    """
    from launch import LaunchDescription
    from launch_ros.actions import Node


    def generate_launch_description() -> LaunchDescription:
        return LaunchDescription([
            Node(package="robot_drivers", executable="stm32_bridge", name="stm32_bridge", output="screen"),
            Node(package="robot_drivers", executable="esp32_bridge", name="esp32_bridge", output="screen"),
            Node(package="robot_teleop", executable="ps5_bridge", name="ps5_bridge", output="screen"),
        ])
    """,
)

write(
    ws / "robot_bringup" / "config" / "robot_ports.yaml",
    """
    stm32_bridge:
      ros__parameters:
        serial_port: /dev/ttyACM0
        baudrate: 115200

    esp32_bridge:
      ros__parameters:
        camera_url: http://esp32cam.local/stream
    """,
)

write(
    ws / "robot_bringup" / "setup.py",
    """
    from setuptools import find_packages, setup

    package_name = "robot_bringup"

    setup(
        name=package_name,
        version="0.0.1",
        packages=find_packages(exclude=["test"]),
        data_files=[
            (
                "share/ament_index/resource_index/packages",
                [f"resource/{package_name}"],
            ),
            (f"share/{package_name}", ["package.xml"]),
            (f"share/{package_name}/launch", ["launch/robot_system.launch.py"]),
            (f"share/{package_name}/config", ["config/robot_ports.yaml"]),
        ],
        install_requires=["setuptools"],
        zip_safe=True,
        maintainer="Rock64 Ranger Team",
        maintainer_email="todo@example.com",
        description="Bringup package for launching full robot stack.",
        license="MIT",
        tests_require=["pytest"],
        entry_points={
            "console_scripts": [],
        },
    )
    """,
)
PY

echo "Workspace scaffold complete at: $WS_ROOT"
echo "Next:"
echo "  cd $WS_ROOT"
echo "  colcon build --symlink-install"
echo "  source install/setup.bash"
echo "  ros2 launch robot_bringup robot_system.launch.py"
