# Tank-Robot root task runner
# Keeps firmware and host builds isolated by default.

SHELL := /bin/bash

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
FIRMWARE_DIR := $(REPO_ROOT)/firmware/stm32_chassis
ifneq (,$(wildcard $(REPO_ROOT)/host_ws/src))
HOST_WS := $(REPO_ROOT)/host_ws
else
HOST_WS := $(REPO_ROOT)/ros2_ws
endif

.PHONY: help stm32-config stm32-build stm32-flash microros-build host-build host-launch host-print

help:
	@echo "Targets:"
	@echo "  stm32-config   Configure STM32 CMake build in firmware tree"
	@echo "  stm32-build    Build STM32 firmware in firmware tree"
	@echo "  stm32-flash    Flash STM32 firmware (requires OpenOCD/ST-Link)"
	@echo "  microros-build Build micro-ROS static library for STM32"
	@echo "  host-build     Build host ROS2 workspace (host_ws preferred)"
	@echo "  host-launch    Launch Rock64 bringup from active host workspace"
	@echo "  host-print     Print selected host workspace"

host-print:
	@echo "HOST_WS=$(HOST_WS)"

stm32-config:
	@cd "$(FIRMWARE_DIR)" && cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake

stm32-build: stm32-config
	@cmake --build "$(FIRMWARE_DIR)/build" -j4

stm32-flash:
	@bash "$(REPO_ROOT)/scripts/flash_stm32.sh"

microros-build:
	@bash "$(REPO_ROOT)/scripts/build_microros.sh"

host-build:
	@cd "$(HOST_WS)" && colcon build --symlink-install

host-launch:
	@cd "$(HOST_WS)" && \
		source /opt/ros/$${ROS_DISTRO:-jazzy}/setup.bash && \
		if [ -f install/setup.bash ]; then source install/setup.bash; fi && \
		ros2 launch robot_bringup rock64_bringup.launch.py host_workspace:="$(HOST_WS)"
