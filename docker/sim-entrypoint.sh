#!/usr/bin/env bash
set -Eeuo pipefail

set +u
source /opt/ros/humble/setup.bash
source /opt/tankrobot/host_ws/install/setup.bash
set -u

export GZ_SIM_HEADLESS="${GZ_SIM_HEADLESS:-1}"

ros2 launch robot_bringup gazebo_telemetry.launch.py gui:=true rviz:=false &
gazebo_pid=$!

cleanup() {
  kill "${gazebo_pid}" 2>/dev/null || true
  wait "${gazebo_pid}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ros2 run foxglove_bridge foxglove_bridge --ros-args \
  -p port:=8765 \
  -p address:=0.0.0.0 \
  -p topic_whitelist:='[".*"]' \
  -p capabilities:='["connectionGraph", "assets"]'
