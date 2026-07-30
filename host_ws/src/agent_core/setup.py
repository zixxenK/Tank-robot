from setuptools import setup

package_name = 'agent_core'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tank Robot Team',
    maintainer_email='dev@example.com',
    description='Autonomous agent core with safety-gated ROS 2 integration',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'safety_gateway = agent_core.safety_gateway:main',
            'agent_planner = agent_core.agent_planner:main',
            'memory_store = agent_core.memory_store:main',
        ],
    },
)
