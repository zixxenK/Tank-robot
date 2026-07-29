#!/bin/bash
# Clean build script to remove LVGL dependencies
# Run this to clean the build directory and reconfigure without LVGL

set -eo pipefail

echo "Cleaning build directory..."
rm -rf build

echo "Reconfiguring without LVGL..."
cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake -DSTM32_ENABLE_LVGL=OFF

echo "Building firmware..."
cmake --build build -j4

echo "Build complete!"
