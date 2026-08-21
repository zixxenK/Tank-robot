#!/usr/bin/env bash
# Check for a runnable ARM GNU toolchain on the current architecture.

set -Eeuo pipefail

echo "Checking for ARM toolchain installation..."

if command -v arm-none-eabi-gcc >/dev/null 2>&1; then
    echo "ARM toolchain found in PATH: $(command -v arm-none-eabi-gcc)"
    arm-none-eabi-gcc --version
    exit 0
fi

echo "ARM toolchain not found in PATH; checking common locations..."
USER_HOME="$(getent passwd "$(id -un)" | cut -d: -f6)"
while IFS= read -r location; do
    if [[ -x "${location}" ]]; then
        echo "Found ARM toolchain at: ${location}"
        echo "Add to PATH with: export PATH=$(dirname "${location}"):\$PATH"
        exit 0
    fi
done < <(find /usr/bin /usr/local/bin /opt "${USER_HOME}" \
    -type f -name arm-none-eabi-gcc -perm -u+x 2>/dev/null)

echo "ARM toolchain not found on $(uname -m)." >&2
echo "Install the supported native packages on Rock64:" >&2
echo "  sudo apt-get install gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib" >&2
echo "Or run scripts/install_toolchain_local.sh on an x86_64 development host." >&2
exit 1
