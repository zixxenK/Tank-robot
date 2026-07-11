from setuptools import find_packages, setup

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
    description="Hardware bridge nodes for STM32 serial and ESP32 camera",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "stm32_serial_bridge = robot_drivers.stm32_serial_bridge:main",
            "esp32_camera_bridge = robot_drivers.esp32_camera_bridge:main",
        ],
    },
)
