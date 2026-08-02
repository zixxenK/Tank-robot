#!/bin/bash
# Check for ARM toolchain installation

echo "Checking for ARM toolchain installation..."

# Check if arm-none-eabi-gcc is in PATH
if command -v arm-none-eabi-gcc &> /dev/null; then
    echo "✅ ARM toolchain found in PATH:"
    which arm-none-eabi-gcc
    arm-none-eabi-gcc --version
    exit 0
fi

# Check common installation locations
echo "❌ ARM toolchain not found in PATH"
echo "Checking common installation locations..."

for location in \
    "/usr/bin/arm-none-eabi-gcc" \
    "/usr/local/bin/arm-none-eabi-gcc" \
    "$HOME/gcc-arm-none-eabi-*/bin/arm-none-eabi-gcc" \
    "/opt/gcc-arm-none-eabi-*/bin/arm-none-eabi-gcc"; do
    
    if ls $location 2>/dev/null; then
        echo "✅ Found ARM toolchain at: $location"
        echo "Add to PATH with: export PATH=$(dirname $location):\$PATH"
        exit 0
    fi
done

echo "❌ ARM toolchain not found in common locations"
echo ""
echo "You need the ARM GNU toolchain to build the STM32 firmware."
echo ""
echo "Option 1: Install locally without sudo:"
echo "  cd ~"
echo "  wget https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2"
echo "  tar -xjf gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2"
echo "  export PATH=\$HOME/gcc-arm-none-eabi-10.3-2021.10/bin:\$PATH"
echo ""
echo "Option 2: Request sudo access for system installation:"
echo "  sudo apt-get install gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib"

exit 1