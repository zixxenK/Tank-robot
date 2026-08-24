from setuptools import find_packages, setup


package_name = "robot_control"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/config", ["config/control_map.yaml"]),
    ],
    install_requires=["setuptools", "PyYAML"],
    zip_safe=True,
    maintainer="Tank Robot Team",
    maintainer_email="todo@example.com",
    description="Shared Tank Robot control-map and tracked-drive math",
    license="MIT",
)
