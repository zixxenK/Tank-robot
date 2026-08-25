param(
  [string]$HostName = "192.168.1.139",
  [string]$UserName = "rock64",
  [int]$LocalPort = 18765,
  [int]$RemotePort = 8765,
  [switch]$NoSlam,
  [switch]$RemoteAccess
)

$ErrorActionPreference = "Stop"

$launchArguments = "use_nav2:=false"
if ($NoSlam) {
  $launchArguments += " use_slam:=false"
}
if ($RemoteAccess) {
  $launchArguments += " remote_access:=true"
}

# The remote bridge runs beside the Rock64 acquisition service.  It must share
# that process's ROS graph; ROS_LOCALHOST_ONLY=1 would isolate the bridge and
# hide the hardware topics (including both camera streams).
$remoteCommand = "set -a; if [ -f /opt/rock64-robot/deployment/systemd/systemd_config.conf ]; then source /opt/rock64-robot/deployment/systemd/systemd_config.conf; fi; set +a; export ROS_DOMAIN_ID=42; export RMW_IMPLEMENTATION=rmw_fastrtps_cpp; export ROS_LOCALHOST_ONLY=0;"
if ($RemoteAccess) {
  $remoteCommand += " export FOXGLOVE_REMOTE_ACCESS=true; "
  $remoteCommand += 'if [ -z "${FOXGLOVE_DEVICE_TOKEN:-}" ]; then echo "[remote_dashboard] FOXGLOVE_DEVICE_TOKEN is not configured in systemd_config.conf" >&2; exit 2; fi;'
}
$remoteCommand += " source /opt/rock64-robot/deployment/scripts/source_host_ws.sh; exec ros2 launch robot_bringup pc_dashboard.launch.py $launchArguments"
$forward = "${LocalPort}:127.0.0.1:${RemotePort}"

Write-Host "[remote_dashboard] Rock64: $UserName@$HostName"
Write-Host "[remote_dashboard] Foxglove: ws://127.0.0.1:$LocalPort"
Write-Host "[remote_dashboard] Stop with Ctrl+C."

& ssh -tt -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -L $forward "$UserName@$HostName" $remoteCommand
exit $LASTEXITCODE
