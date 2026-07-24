#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y locales curl gnupg2 lsb-release software-properties-common
locale-gen en_US en_US.UTF-8 || true
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 || true
add-apt-repository universe -y
mkdir -p /usr/share/keyrings
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
cat >/etc/apt/sources.list.d/ros2.list <<EOF
# ROS2 repo
deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release; echo $UBUNTU_CODENAME) main
EOF
apt-get update
apt-get install -y ros-humble-desktop python3-colcon-common-extensions python3-rosdep python3-vcstool build-essential
rosdep init || true
rosdep update || true
test -f /opt/ros/humble/setup.bash
echo "ROS2 Humble install complete"
