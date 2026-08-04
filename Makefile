# Tank-Robot root task runner
# Keeps firmware and host builds isolated by default.

SHELL := /bin/bash

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
FIRMWARE_DIR := $(REPO_ROOT)/firmware/stm32_chassis
HOST_WS := $(REPO_ROOT)/host_ws

.PHONY: help stm32-config stm32-build stm32-flash host-build host-launch host-print host-sim host-hardware host-motor-test host-teleop host-teleop-ps5 host-unify host-unify-hw onecmd

help:
	@echo "Targets:"
	@echo "  stm32-config   Configure STM32 CMake build in firmware tree"
	@echo "  stm32-build    Build STM32 firmware in firmware tree"
	@echo "  stm32-flash    Flash STM32 firmware (requires OpenOCD/ST-Link)"
	@echo "  host-build     Build host ROS2 workspace (host_ws preferred)"
	@echo "  host-launch    Launch Rock64 bringup from active host workspace"
	@echo "  host-sim       One-shot install deps + build + Gazebo telemetry launch"
	@echo "  host-hardware  One-shot build + hardware bringup launch"
	@echo "  host-motor-test One-shot build + hardware bringup + raised-track motor test"
	@echo "  host-teleop    One-shot build + keyboard teleop launch"
	@echo "  host-teleop-ps5 One-shot build + PS5 teleop launch"
	@echo "  onecmd         One-command Gazebo telemetry launch from the host workspace"
	@echo "  host-print     Print selected host workspace"

host-print:
	@echo "HOST_WS=$(HOST_WS)"

stm32-config:
	@cd "$(FIRMWARE_DIR)" && cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake

stm32-build: stm32-config
	@cmake --build "$(FIRMWARE_DIR)/build" -j4

stm32-flash:
	@bash "$(REPO_ROOT)/scripts/flash_stm32.sh"

host-build:
	@cd "$(HOST_WS)" && colcon build --symlink-install

host-launch:
	@cd "$(HOST_WS)" && \
		source /opt/ros/$${ROS_DISTRO:-humble}/setup.bash && \
		if [ -f install/setup.bash ]; then source install/setup.bash; fi && \
		ros2 launch robot_bringup rock64_bringup.launch.py host_workspace:="$(HOST_WS)"

host-sim:
	@bash "$(REPO_ROOT)/scripts/unify_host_ws.sh" --mode sim

host-hardware:
	@bash "$(REPO_ROOT)/scripts/unify_host_ws.sh" --mode hardware --no-install-deps

host-motor-test:
	@cd "$(HOST_WS)" && \
		source /opt/ros/$${ROS_DISTRO:-humble}/setup.bash && \
		if [ -f install/setup.bash ]; then source install/setup.bash; fi && \
		ros2 launch robot_bringup rock64_bringup.launch.py \
			host_workspace:="$(HOST_WS)" \
			use_teleop:=false \
			run_motor_bringup_test:=true

host-teleop:
	@bash "$(REPO_ROOT)/scripts/unify_host_ws.sh" --mode teleop --teleop keyboard --no-install-deps

host-teleop-ps5:
	@bash "$(REPO_ROOT)/scripts/unify_host_ws.sh" --mode teleop --teleop ps5 --no-install-deps

host-unify: host-sim

host-unify-hw: host-hardware

onecmd:
	@cd "$(HOST_WS)" && \
		. /opt/ros/$${ROS_DISTRO:-humble}/setup.bash && \
		if [ -f install/setup.bash ]; then . install/setup.bash; fi && \
		ros2 launch robot_bringup gazebo_telemetry.launch.py
