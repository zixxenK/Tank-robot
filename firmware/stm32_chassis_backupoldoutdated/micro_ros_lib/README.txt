Place the precompiled micro-ROS static library in this folder.

Required when firmware/stm32_chassis/CMakeLists.txt builds with:
	-DSTM32_ENABLE_MICROROS=ON

Expected outputs after a successful micro-ROS build:
	micro_ros_lib/libmicroros.a
	micro_ros_lib/include/
	micro_ros_lib/colcon.meta

Build the library (Linux host with ROS 2 installed):
	# From repo root
	bash scripts/build_microros.sh

Requirements:
	- ROS 2 Jazzy (Ubuntu 24.04) or Humble (Ubuntu 22.04)
	- gcc-arm-none-eabi
	- cmake, git, colcon, rosdep

Reconfigure and build STM32 firmware:
	cd firmware/stm32_chassis
	cmake -B build \
		-DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake \
		-DSTM32_ENABLE_MICROROS=ON
	cmake --build build -j4

Flash/debug path for STM32 is ST-Link + OpenOCD.
PlatformIO is not used for STM32 firmware programming in this repository.
