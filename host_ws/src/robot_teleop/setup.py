# pyright: reportMissingTypeStubs=false

from setuptools import find_packages, setup  # type: ignore[import-untyped]

package_name = "robot_teleop"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages",
         [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Rock64 Ranger Team",
    maintainer_email="todo@example.com",
    description="PS5 controller and keyboard teleop nodes",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "ps5_ros_bridge    = robot_teleop.ps5_ros_bridge:main",
            "keyboard_teleop   = robot_teleop.keyboard_teleop:main",
            "cmd_vel_to_tracks = robot_teleop.cmd_vel_to_tracks:main",
            "ps5_device_check  = robot_teleop.ps5_device_check:main",
        ],
    },
)
