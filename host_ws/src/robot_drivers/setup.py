# pyright: reportMissingTypeStubs=false

from setuptools import find_packages, setup  # type: ignore[import-untyped]

package_name = "robot_drivers"

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
    description="Hardware bridge and STL-50B2 LiDAR nodes",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "stm32_hardened_bridge = robot_drivers.stm32_hardened_bridge:main",
            "esp32_camera_bridge = robot_drivers.esp32_camera_bridge:main",
            "motor_bringup_test = robot_drivers.motor_bringup_test:main",
            "stm32_selftest_cli = robot_drivers.stm32_selftest_cli:main",
            "telemetry_markers = robot_drivers.telemetry_markers:main",
            "stl50b2_lidar = robot_drivers.stl50b2_lidar:main",
            "usb_webcam_bridge = robot_drivers.usb_webcam_bridge:main",
        ],
    },
)
