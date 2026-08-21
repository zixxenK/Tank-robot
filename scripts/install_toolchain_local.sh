#!/usr/bin/env bash
# Install ARM toolchain locally without sudo

set -Eeuo pipefail

echo "Installing ARM toolchain locally in home directory..."

# Prefer a native/system toolchain. The Rock64 is aarch64; downloading the
# legacy x86_64 archive there would create a toolchain that cannot execute.
if command -v arm-none-eabi-gcc >/dev/null 2>&1; then
    echo "ARM toolchain already available: $(command -v arm-none-eabi-gcc)"
    arm-none-eabi-gcc --version
    exit 0
fi

ARCH="$(uname -m)"
if [[ "${ARCH}" != "x86_64" && "${ARCH}" != "amd64" ]]; then
    echo "ERROR: no ARM toolchain found on ${ARCH}." >&2
    echo "Install the native distro packages instead:" >&2
    echo "  sudo apt-get install gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib" >&2
    exit 2
fi

USER_HOME="$(getent passwd "$(id -un)" | cut -d: -f6)"
TOOLCHAIN_ROOT="${ARM_TOOLCHAIN_ROOT:-${USER_HOME}/tools}"
TOOLCHAIN_DIR="${TOOLCHAIN_ROOT}/gcc-arm-none-eabi-10.3-2021.10"
ARCHIVE="gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2"
mkdir -p "${TOOLCHAIN_ROOT}"

# Download ARM toolchain (this is about 100MB)
cd "${TOOLCHAIN_ROOT}"
if [ ! -d "${TOOLCHAIN_DIR}" ]; then
    echo "Downloading ARM toolchain (this may take a few minutes)..."
    wget -O "${ARCHIVE}" "https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/${ARCHIVE}"
    
    echo "Extracting toolchain..."
    tar -xjf "${ARCHIVE}"
    
    # Clean up download
    rm -f "${ARCHIVE}"
else
    echo "Toolchain already downloaded and extracted."
fi

# Add to PATH for current session
export PATH="${TOOLCHAIN_DIR}/bin:${PATH}"

# Add to .bashrc for persistence
SHELL_RC="${USER_HOME}/.bashrc"
if ! grep -qF "${TOOLCHAIN_DIR}/bin" "${SHELL_RC}" 2>/dev/null; then
    {
        echo ""
        echo "# ARM toolchain for STM32 firmware"
        echo "export PATH=\"${TOOLCHAIN_DIR}/bin:\$PATH\""
    } >> "${SHELL_RC}"
    echo "Added ARM toolchain to PATH in ${SHELL_RC}"
fi

# Verify installation
echo ""
echo "Verifying installation..."
arm-none-eabi-gcc --version

echo ""
echo "✅ ARM toolchain installed successfully!"
echo "Please run: source ${SHELL_RC}"
echo "Or log out and log back in for PATH changes to take effect."
