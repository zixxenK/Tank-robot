#!/bin/bash
# Install ARM toolchain locally without sudo

set -e

echo "Installing ARM toolchain locally in home directory..."

# Create directory for toolchain
mkdir -p ~/tools

# Download ARM toolchain (this is about 100MB)
cd ~/tools
if [ ! -d "gcc-arm-none-eabi-10.3-2021.10" ]; then
    echo "Downloading ARM toolchain (this may take a few minutes)..."
    wget https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2
    
    echo "Extracting toolchain..."
    tar -xjf gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2
    
    # Clean up download
    rm gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2
else
    echo "Toolchain already downloaded and extracted."
fi

# Add to PATH for current session
export PATH=$HOME/tools/gcc-arm-none-eabi-10.3-2021.10/bin:$PATH

# Add to .bashrc for persistence
if ! grep -q "gcc-arm-none-eabi-10.3-2021.10/bin" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# ARM toolchain for micro-ROS" >> ~/.bashrc
    echo "export PATH=\$HOME/tools/gcc-arm-none-eabi-10.3-2021.10/bin:\$PATH" >> ~/.bashrc
    echo "Added ARM toolchain to PATH in ~/.bashrc"
fi

# Verify installation
echo ""
echo "Verifying installation..."
arm-none-eabi-gcc --version

echo ""
echo "✅ ARM toolchain installed successfully!"
echo "Please run: source ~/.bashrc"
echo "Or log out and log back in for PATH changes to take effect."