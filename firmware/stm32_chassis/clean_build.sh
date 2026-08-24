#!/bin/bash
# Clean and rebuild the canonical STM32 Debug preset.

set -eo pipefail

echo "Cleaning build directory..."
rm -rf build

echo "Reconfiguring the Debug preset..."
cmake --preset Debug

echo "Building firmware..."
cmake --build --preset Debug --parallel 4

echo "Build complete!"
