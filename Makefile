# Tank-Robot root task runner
# Keeps firmware and host builds isolated by default.

SHELL := /bin/bash

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
FIRMWARE_DIR := $(REPO_ROOT)/firmware/stm32_chassis
HOST_WS := $(REPO_ROOT)/host_ws
PYTHON ?= python3

.PHONY: help e2e test stm32-config stm32-build stm32-flash host-build host-launch host-print host-sim host-hardware host-motor-test host-teleop host-teleop-ps5 host-unify host-unify-hw onecmd onecmd-sim hardware-acceptance hardware-acceptance-raised robot-start motor-forward motor-back motor-stop motor-sequence rock64-update

help:
	@echo "Targets:"
	@echo "  e2e             Run complete one-shot E2E mission with Mission Report"
	@echo "  test            Run host unit tests with repository ROS stubs"
	@echo "  stm32-config   Configure STM32 CMake build in firmware tree"
	@echo "  stm32-build    Build STM32 firmware in firmware tree"
	@echo "  stm32-flash    Rock64-only STM32 flash guard/delegation target"
	@echo "  rock64-update  Build host + STM32 and flash from the updated Rock64"
	@echo "  host-build     Build host ROS2 workspace (host_ws preferred)"
	@echo "  host-launch    Launch Rock64 bringup from active host workspace"
	@echo "  host-sim       One-shot install deps + build + Gazebo telemetry launch"
	@echo "  host-hardware  One-shot build + hardware bringup launch"
	@echo "  host-motor-test One-shot build + hardware bringup + raised-track motor test"
	@echo "  host-teleop    One-shot build + keyboard teleop launch"
	@echo "  host-teleop-ps5 One-shot build + PS5 teleop launch"
	@echo "  motor-forward  Send guarded forward command to both tracks"
	@echo "  motor-back     Send guarded backward command to both tracks"
	@echo "  motor-stop     Send stop command to both tracks"
	@echo "  motor-sequence Run forward/stop/back/stop sequence"
	@echo "  robot-start    Start Rock64 ROS2/STM32 base without PS5"
	@echo "  onecmd         Start all Rock64 hardware in one persistent ROS 2 launch"
	@echo "  onecmd-sim     Launch Gazebo telemetry instead of physical hardware"
	@echo "  hardware-acceptance Run ordered non-motion checks on the running stack"
	@echo "  hardware-acceptance-raised Include guarded motor checks (tracks raised)"
	@echo "  host-print     Print selected host workspace"

host-print:
	@echo "HOST_WS=$(HOST_WS)"

e2e:
	@if command -v python3 >/dev/null 2>&1; then \
		python3 "$(REPO_ROOT)/scripts/e2e_mission.py"; \
	else \
		python "$(REPO_ROOT)/scripts/e2e_mission.py"; \
	fi

test:
	@PYTHONPATH="$(REPO_ROOT)/stubs:$(HOST_WS)/src/agent_core:$(HOST_WS)/src/robot_drivers:$(HOST_WS)/src/robot_teleop:$(HOST_WS)/src/robot_audio:$(HOST_WS)/src/robot_control:$(HOST_WS)/src/navigation:$(HOST_WS)/src/perception:$(HOST_WS)/src/telemetry_logger:$(HOST_WS)/src/terrain_adaptation" \
		$(PYTHON) -m pytest tests \
			"$(HOST_WS)/src/agent_core/test" \
			"$(HOST_WS)/src/robot_drivers/test" \
			"$(HOST_WS)/src/robot_teleop/test" \
			"$(HOST_WS)/src/robot_audio/test" \
			"$(HOST_WS)/src/robot_control/test" \
			--ignore="$(HOST_WS)/src/agent_core/test/test_flake8.py" \
			--ignore="$(HOST_WS)/src/agent_core/test/test_pep257.py" \
			--ignore="$(HOST_WS)/src/robot_drivers/test/test_flake8.py" \
			--ignore="$(HOST_WS)/src/robot_drivers/test/test_pep257.py" -q

stm32-config:
	@cd "$(FIRMWARE_DIR)" && cmake --preset Debug

stm32-build: stm32-config
	@cd "$(FIRMWARE_DIR)" && cmake --build --preset Debug --parallel 4

stm32-flash:
	@if [ "$$(uname -m)" = "aarch64" ]; then \
		bash "$(REPO_ROOT)/deployment/scripts/rock64_update_and_flash.sh"; \
	else \
		echo "Direct STM32 flashing from a PC is disabled."; \
		echo "Run the Rock64-owned workflow from Windows PowerShell:"; \
		echo "  .\\scripts\\deploy_rock64.ps1"; \
		exit 1; \
	fi

rock64-update:
	@bash "$(REPO_ROOT)/deployment/scripts/rock64_update_and_flash.sh"

host-build:
	@set +u; \
		source "$(REPO_ROOT)/deployment/scripts/source_host_ws.sh"; \
		set -u; \
		cd "$(HOST_WS)" && colcon build --symlink-install

host-launch:
	@set +u; \
		source "$(REPO_ROOT)/deployment/scripts/source_host_ws.sh"; \
		set -u; \
		cd "$(HOST_WS)" && \
		ros2 launch robot_bringup rock64_bringup.launch.py

host-sim:
	@bash "$(REPO_ROOT)/scripts/unify_host_ws.sh" --mode sim

host-hardware:
	@bash "$(REPO_ROOT)/scripts/unify_host_ws.sh" --mode hardware --no-install-deps

host-motor-test:
	@set +u; \
		source "$(REPO_ROOT)/deployment/scripts/source_host_ws.sh"; \
		set -u; \
		cd "$(HOST_WS)" && \
		ros2 launch robot_bringup rock64_bringup.launch.py \
			use_teleop:=false \
			run_motor_bringup_test:=true

host-teleop:
	@bash "$(REPO_ROOT)/scripts/unify_host_ws.sh" --mode teleop --teleop keyboard --no-install-deps

host-teleop-ps5:
	@bash "$(REPO_ROOT)/scripts/unify_host_ws.sh" --mode teleop --teleop ps5 --no-install-deps

robot-start:
	@bash "$(REPO_ROOT)/scripts/robot_base_start.sh"

motor-forward:
	@bash "$(REPO_ROOT)/scripts/motor_forward.sh" --confirm

motor-back:
	@bash "$(REPO_ROOT)/scripts/motor_back.sh" --confirm

motor-stop:
	@bash "$(REPO_ROOT)/scripts/motor_stop.sh"

motor-sequence:
	@bash "$(REPO_ROOT)/scripts/motor_test_sequence.sh" --confirm 1

host-unify: host-sim

host-unify-hw: host-hardware

onecmd:
	@bash "$(REPO_ROOT)/scripts/onecmd.sh"

onecmd-sim:
	@bash "$(REPO_ROOT)/scripts/onecmd.sh" --sim

hardware-acceptance:
	@bash "$(REPO_ROOT)/scripts/hardware_acceptance.sh"

hardware-acceptance-raised:
	@bash "$(REPO_ROOT)/scripts/hardware_acceptance.sh" --tracks-raised
