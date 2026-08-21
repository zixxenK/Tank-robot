#!/usr/bin/env bash
# Remove stale operator-launched ROS processes without touching the
# rock64-robot.service hardware owner. This is scoped to the current user and
# known ROS/robot process names.
set -Eeuo pipefail

service_main=""
if command -v systemctl >/dev/null 2>&1; then
  service_main="$(systemctl show -p MainPID --value rock64-robot.service 2>/dev/null || true)"
fi

stale_pids=()
while read -r pid user args; do
  [[ -n "${pid}" && "${pid}" != "$$" && "${pid}" != "${PPID}" ]] || continue
  [[ "${user}" == "$(id -un)" ]] || continue
  [[ "${pid}" == "${service_main}" ]] && continue
  if [[ -r "/proc/${pid}/cgroup" ]] && grep -q 'rock64-robot.service' "/proc/${pid}/cgroup"; then
    continue
  fi
  case "${args}" in
    *ros2\ launch*|*ros2\ run*|*/robot_drivers/*|*/robot_teleop/*|*/robot_bringup/*|*rqt_image_view*)
      stale_pids+=("${pid}") ;;
  esac
done < <(ps -eo pid=,user=,args=)

if ((${#stale_pids[@]})); then
  echo "[cleanup_runtime] stopping stale operator ROS processes: ${stale_pids[*]}"
  kill -TERM "${stale_pids[@]}" 2>/dev/null || true
  sleep 1
  kill -KILL "${stale_pids[@]}" 2>/dev/null || true
else
  echo "[cleanup_runtime] no stale operator ROS processes found"
fi

if command -v ros2 >/dev/null 2>&1; then
  ros2 daemon stop >/dev/null 2>&1 || true
fi

echo "[cleanup_runtime] canonical workspace is ${HOST_WS_PATH:-/opt/rock64-robot/host_ws}"
