import os
from glob import glob
from setuptools import find_packages, setup

package_name = "robot_audio"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages",
         [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Tank Robot Team",
    maintainer_email="dev@example.com",
    description="Modular buzzer song creator and waypoint music triggers for Tank Robot",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "buzzer_song_creator   = robot_audio.buzzer_song_creator:main",
            "waypoint_music_trigger = robot_audio.waypoint_music_trigger:main",
        ],
    },
)
