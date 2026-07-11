#!/usr/bin/env bash
# install-toolchain.sh
# Installs the ARM bare-metal GCC toolchain and STM32 build dependencies
# into the devcontainer image on first create.
set -euo pipefail

echo "[toolchain] Installing ARM GCC toolchain and build tools..."
apt-get update -qq
apt-get install -y --no-install-recommends \
  gcc-arm-none-eabi \
  binutils-arm-none-eabi \
  libnewlib-arm-none-eabi \
  cmake \
  ninja-build \
  stlink-tools \
  openocd \
  gdb-multiarch \
  python3-pip \
  python3-colcon-common-extensions \
  python3-rosdep \
  ros-jazzy-rmw-fastrtps-cpp

echo "[toolchain] ARM toolchain installation complete."
arm-none-eabi-gcc --version
