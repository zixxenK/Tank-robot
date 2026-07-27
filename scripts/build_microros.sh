#!/usr/bin/env bash
# build_microros.sh — Build the micro-ROS static library for STM32F407 (Cortex-M4 hard-float).
#
# Run from anywhere inside the repo:
#   bash scripts/build_microros.sh
#
# Outputs written into the repo:
#   firmware/stm32_chassis/micro_ros_lib/libmicroros.a
#   firmware/stm32_chassis/micro_ros_lib/include/
#
# Requirements on the build host (Rock64 or Linux dev box):
#   - ROS 2 Humble (Ubuntu 22.04) installed
#   - arm-none-eabi-gcc in PATH  (sudo apt-get install gcc-arm-none-eabi)
#   - cmake, git, colcon, rosdep, python3-pip
#
# The workspace is cached in firmware/stm32_chassis/.cache/microros-build/
# so subsequent runs only rebuild if you delete that folder.

# Some launch paths may end up invoking this script with /bin/sh.
# Re-exec under bash before enabling bash-specific options.
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -euo pipefail

on_error() {
    local exit_code=$?
    echo ""
    echo "[build_microros] ERROR: build failed (exit code ${exit_code})." >&2
    if [[ -n "${UROS_WS:-}" && -d "${UROS_WS}/log/latest" ]]; then
        echo "[build_microros] Last colcon log directory: ${UROS_WS}/log/latest" >&2
    fi
    exit "${exit_code}"
}

trap on_error ERR

source_nounset_safe() {
    local had_nounset=0
    if [[ $- == *u* ]]; then
        had_nounset=1
        set +u
    fi

    # shellcheck source=/dev/null
    source "$1"

    if [[ "${had_nounset}" -eq 1 ]]; then
        set -u
    fi
}

# ── Resolve repo paths ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MICRO_ROS_LIB_DIR="${REPO_ROOT}/firmware/stm32_chassis/micro_ros_lib"
COLCON_META="${MICRO_ROS_LIB_DIR}/colcon.meta"
CACHE_DIR="${REPO_ROOT}/firmware/stm32_chassis/.cache/microros-build"
UROS_WS="${CACHE_DIR}/uros_ws"
MICROROS_PRUNE_OPTIONAL_PACKAGES="${MICROROS_PRUNE_OPTIONAL_PACKAGES:-1}"

add_colcon_ignore_if_exists() {
    local dir="$1"
    if [[ -d "${dir}" ]]; then
        touch "${dir}/COLCON_IGNORE"
        echo "      Pruned optional package path: ${dir}"
    fi
}

sync_colcon_meta_into_mcu_ws() {
    local mcu_ws_meta="${UROS_WS}/firmware/mcu_ws/colcon.meta"
    mkdir -p "$(dirname "${mcu_ws_meta}")"
    cp "${COLCON_META}" "${mcu_ws_meta}"
    echo "      Synced STM32 colcon.meta -> ${mcu_ws_meta}"
}

ensure_colcon_meta() {
    if [[ -f "${COLCON_META}" ]]; then
        return
    fi

    echo "[build_microros] No custom colcon.meta found at ${COLCON_META}."
    echo "[build_microros] Writing STM32-safe fallback colcon.meta (rcutils CLOCK_MONOTONIC workaround)."
    mkdir -p "${MICRO_ROS_LIB_DIR}"

    cat > "${COLCON_META}" <<'COLCON_META_EOF'
{
    "names": {
        "tracetools": {
            "cmake-args": [
                "-DTRACETOOLS_DISABLED=ON",
                "-DTRACETOOLS_STATUS_CHECKING_TOOL=OFF"
            ]
        },
        "rosidl_typesupport": {
            "cmake-args": [
                "-DROSIDL_TYPESUPPORT_SINGLE_TYPESUPPORT=ON"
            ]
        },
        "rcl": {
            "cmake-args": [
                "-DBUILD_TESTING=OFF",
                "-DRCL_MICROROS=ON"
            ]
        },
        "rcutils": {
            "cmake-args": [
                "-DENABLE_TESTING=OFF",
                "-DRCUTILS_NO_FILESYSTEM=ON",
                "-DRCUTILS_NO_THREAD_SUPPORT=ON",
                "-DRCUTILS_NO_64_ATOMIC=ON",
                "-DRCUTILS_AVOID_DYNAMIC_ALLOCATION=ON",
                "-DCMAKE_C_FLAGS=-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -fdata-sections -ffunction-sections -fno-exceptions -O2 -DNDEBUG -D_POSIX_C_SOURCE=200809L -DCLOCK_MONOTONIC=CLOCK_REALTIME -DCLOCK_MONOTONIC_RAW=CLOCK_REALTIME"
            ]
        },
        "rmw_microxrcedds": {
            "cmake-args": [
                "-DRMW_UXRCE_MAX_NODES=1",
                "-DRMW_UXRCE_MAX_PUBLISHERS=0",
                "-DRMW_UXRCE_MAX_SUBSCRIPTIONS=1",
                "-DRMW_UXRCE_MAX_SERVICES=0",
                "-DRMW_UXRCE_MAX_CLIENTS=0",
                "-DRMW_UXRCE_MAX_HISTORY=4",
                "-DRMW_UXRCE_TRANSPORT=custom",
                "-DCMAKE_C_FLAGS=-Wno-pedantic"
            ]
        },
        "microxrcedds_client": {
            "cmake-args": [
                "-DUCLIENT_PIC=OFF",
                "-DUCLIENT_PROFILE_DISCOVERY=OFF",
                "-DUCLIENT_PROFILE_UDP=OFF",
                "-DUCLIENT_PROFILE_TCP=OFF",
                "-DUCLIENT_PROFILE_SERIAL=OFF",
                "-DUCLIENT_PROFILE_CUSTOM_TRANSPORT=ON",
                "-DUCLIENT_PROFILE_STREAM_FRAMING=ON",
                "-DUCLIENT_MAX_SESSION_CONNECTION_ATTEMPTS=4294967295U",
                "-DCMAKE_C_FLAGS=-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -fdata-sections -ffunction-sections -fno-exceptions -O2 -DNDEBUG -D_POSIX_C_SOURCE=200809L -Wno-implicit-function-declaration -Wno-sign-conversion"
            ]
        }
    }
}
COLCON_META_EOF
}

# ── Preflight checks ───────────────────────────────────────────────────────
echo "[build_microros] Checking prerequisites..."

if ! command -v arm-none-eabi-gcc &>/dev/null; then
    echo "ERROR: arm-none-eabi-gcc not found." >&2
    echo "  sudo apt-get install gcc-arm-none-eabi" >&2
    exit 1
fi
echo "  arm-none-eabi-gcc : $(arm-none-eabi-gcc --version | head -1)"

ARM_STRING_H_PATH="$(arm-none-eabi-gcc -print-file-name=include/string.h 2>/dev/null || true)"
ARM_NEWLIB_CANDIDATE_1="/usr/arm-none-eabi/include/string.h"
ARM_NEWLIB_CANDIDATE_2="/usr/lib/arm-none-eabi/newlib/include/string.h"
ARM_NEWLIB_CANDIDATE_3="/usr/include/newlib/string.h"

HAS_ARM_STRING_H=0
if [[ -n "${ARM_STRING_H_PATH}" && "${ARM_STRING_H_PATH}" != "include/string.h" && -f "${ARM_STRING_H_PATH}" ]]; then
    HAS_ARM_STRING_H=1
elif [[ -f "${ARM_NEWLIB_CANDIDATE_1}" || -f "${ARM_NEWLIB_CANDIDATE_2}" || -f "${ARM_NEWLIB_CANDIDATE_3}" ]]; then
    HAS_ARM_STRING_H=1
fi

# Final check: verify the compiler can preprocess and compile a C file using <string.h>.
if [[ "${HAS_ARM_STRING_H}" -eq 0 ]]; then
    TMP_CHECK_DIR="$(mktemp -d)"
    cat > "${TMP_CHECK_DIR}/newlib_probe.c" <<'NEWLIB_PROBE_EOF'
#include <string.h>
int main(void) { return 0; }
NEWLIB_PROBE_EOF

    if arm-none-eabi-gcc -x c -c "${TMP_CHECK_DIR}/newlib_probe.c" -o "${TMP_CHECK_DIR}/newlib_probe.o" >/dev/null 2>&1; then
        HAS_ARM_STRING_H=1
    fi
    rm -rf "${TMP_CHECK_DIR}"
fi

if [[ "${HAS_ARM_STRING_H}" -ne 1 ]]; then
    echo "ERROR: ARM C runtime headers are not usable by arm-none-eabi-gcc (<string.h> not found)." >&2
    echo "  Try: sudo apt-get install --reinstall gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib" >&2
    echo "  If still failing on Armbian, also install: sudo apt-get install libnewlib-dev" >&2
    exit 1
fi

if ! command -v cmake &>/dev/null; then
    echo "ERROR: cmake not found — install via apt-get." >&2; exit 1
fi

if ! command -v colcon &>/dev/null; then
    echo "ERROR: colcon not found." >&2
    echo "  pip3 install colcon-common-extensions" >&2
    exit 1
fi

# ── Detect / source ROS 2 ─────────────────────────────────────────────────
if [[ -z "${ROS_DISTRO:-}" || "${ROS_DISTRO}" == "auto" ]]; then
    ubuntu_ver="$(lsb_release -rs 2>/dev/null || echo "0")"
    case "${ubuntu_ver}" in
        22.*) ROS_DISTRO=humble ;;
        *)
            echo "ERROR: Cannot detect ROS2 distro from Ubuntu ${ubuntu_ver}." >&2
            echo "  Policy path is Ubuntu 22.04 + ROS2 humble." >&2
            echo "  Export ROS_DISTRO=humble and re-run." >&2
            exit 1
            ;;
    esac
fi

if [[ "${ROS_DISTRO}" != "humble" ]]; then
    echo "ERROR: Only ROS2 humble is supported by this repository policy (requested: ${ROS_DISTRO})." >&2
    exit 1
fi

ROS_SETUP="/opt/ros/${ROS_DISTRO}/setup.bash"
if [[ ! -f "${ROS_SETUP}" ]]; then
    echo "ERROR: ROS 2 ${ROS_DISTRO} not found at ${ROS_SETUP}" >&2
    exit 1
fi
source_nounset_safe "${ROS_SETUP}"
ensure_colcon_meta
echo "  ROS 2 distro      : ${ROS_DISTRO}"
echo "  Build workspace   : ${UROS_WS}"
echo ""

# ── Step 1: Clone micro_ros_setup ─────────────────────────────────────────
mkdir -p "${UROS_WS}/src"

if [[ ! -d "${UROS_WS}/src/micro_ros_setup/.git" ]]; then
    echo "[1/5] Cloning micro_ros_setup (branch: ${ROS_DISTRO})..."
    git clone --depth 1 \
        -b "${ROS_DISTRO}" \
        https://github.com/micro-ROS/micro_ros_setup.git \
        "${UROS_WS}/src/micro_ros_setup"
else
    echo "[1/5] micro_ros_setup already cloned — skipping."
fi

# ── Step 2: Build micro_ros_setup ─────────────────────────────────────────
pushd "${UROS_WS}" > /dev/null

echo "[2/5] Installing rosdep deps and building micro_ros_setup..."
rosdep update --rosdistro "${ROS_DISTRO}" -q 2>/dev/null || true
# Keep rosdep scope narrow so stale cached repos do not pull extra host-side tooling.
rosdep install --from-paths src/micro_ros_setup --ignore-src -y -q --rosdistro "${ROS_DISTRO}"
colcon build \
    --packages-select micro_ros_setup \
    --cmake-args -DCMAKE_BUILD_TYPE=Release \
    --event-handlers console_cohesion+
source_nounset_safe install/setup.bash

# ── Step 3: Create firmware workspace (generate_lib platform) ─────────────
if [[ ! -d firmware ]]; then
    echo "[3/5] Creating micro-ROS firmware workspace..."
    ros2 run micro_ros_setup create_firmware_ws.sh generate_lib
else
    echo "[3/5] Firmware workspace already exists — skipping create."
fi

if [[ "${MICROROS_PRUNE_OPTIONAL_PACKAGES}" == "1" ]]; then
    echo "[3.5/5] Pruning optional ROS2 packages not required for STM32 static lib..."
    add_colcon_ignore_if_exists "${UROS_WS}/firmware/mcu_ws/ros2/ros2_tracing"
    add_colcon_ignore_if_exists "${UROS_WS}/firmware/mcu_ws/ros2/test_interface_files"
    add_colcon_ignore_if_exists "${UROS_WS}/firmware/mcu_ws/ros2/rosidl_dynamic_typesupport"
fi

# ── Step 4: Write the STM32F407 cross-compilation toolchain file ──────────
echo "[4/5] Writing STM32F407 CMake toolchain..."
TOOLCHAIN_FILE="${UROS_WS}/firmware/stm32f407_toolchain.cmake"
cat > "${TOOLCHAIN_FILE}" <<'TOOLCHAIN_EOF'
# Cross-compilation toolchain for STM32F407 — Cortex-M4 hard-float
cmake_minimum_required(VERSION 3.16)

set(CMAKE_SYSTEM_NAME   Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(CMAKE_C_COMPILER   arm-none-eabi-gcc)
set(CMAKE_CXX_COMPILER arm-none-eabi-g++)
set(CMAKE_ASM_COMPILER arm-none-eabi-gcc)
set(CMAKE_AR           arm-none-eabi-ar   CACHE FILEPATH "")
set(CMAKE_RANLIB       arm-none-eabi-ranlib CACHE FILEPATH "")

# Suppress CMake link-stage try_compile tests (no OS to run them)
set(CMAKE_C_COMPILER_WORKS   1 CACHE INTERNAL "")
set(CMAKE_CXX_COMPILER_WORKS 1 CACHE INTERNAL "")
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(MCU_FLAGS
    "-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard")

set(COMMON_FLAGS
    "${MCU_FLAGS}"
    " -fdata-sections -ffunction-sections"
    " -fno-exceptions"
    " -O2 -DNDEBUG")

string(APPEND CMAKE_C_FLAGS_INIT   " ${MCU_FLAGS} -fdata-sections -ffunction-sections -fno-exceptions -O2 -DNDEBUG")
string(APPEND CMAKE_CXX_FLAGS_INIT " ${MCU_FLAGS} -fdata-sections -ffunction-sections -fno-exceptions -fno-rtti -O2 -DNDEBUG")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
TOOLCHAIN_EOF

# ── Step 5: Build the static library ──────────────────────────────────────
echo "[5/5] Building micro-ROS static library (this takes several minutes)..."

# Some micro_ros_setup versions still consume firmware/mcu_ws/colcon.meta by default.
# Keep that path synchronized so rcutils and RMW options are always applied.
sync_colcon_meta_into_mcu_ws

# generate_lib expects positional args: <toolchain_file> [colcon_meta_file]
if [[ -f "${COLCON_META}" ]]; then
    echo "      Using colcon.meta: ${COLCON_META}"
    ros2 run micro_ros_setup build_firmware.sh "${TOOLCHAIN_FILE}" "${COLCON_META}"
else
    ros2 run micro_ros_setup build_firmware.sh "${TOOLCHAIN_FILE}"
fi

popd > /dev/null

# ── Locate and copy build artifacts ───────────────────────────────────────
echo ""
echo "Locating build artifacts..."

FIRMWARE_BUILD="${UROS_WS}/firmware/build"

# libmicroros.a
if [[ ! -f "${FIRMWARE_BUILD}/libmicroros.a" ]]; then
    echo "ERROR: libmicroros.a not found at ${FIRMWARE_BUILD}" >&2
    echo "  Contents of ${FIRMWARE_BUILD}:" >&2
    ls -la "${FIRMWARE_BUILD}" 2>/dev/null || echo "  (directory missing)" >&2
    exit 1
fi

# Install into micro_ros_lib/
rm -rf "${MICRO_ROS_LIB_DIR}/include"
mkdir -p "${MICRO_ROS_LIB_DIR}/include"
cp "${FIRMWARE_BUILD}/libmicroros.a" "${MICRO_ROS_LIB_DIR}/"

# Headers can live in include/ or micro_ros_src/ depending on micro_ros_setup version
HEADER_COPIED=0
for inc_dir in \
    "${FIRMWARE_BUILD}/include" \
    "${FIRMWARE_BUILD}/micro_ros_src" \
    "${FIRMWARE_BUILD}/firmware/include"
do
    if [[ -d "${inc_dir}" ]]; then
        cp -r "${inc_dir}/." "${MICRO_ROS_LIB_DIR}/include/"
        HEADER_COPIED=1
    fi
done

if [[ "${HEADER_COPIED}" -eq 0 ]]; then
    echo "WARNING: Could not locate micro-ROS headers.  Check ${FIRMWARE_BUILD}." >&2
    echo "  Copy the include/ folder manually into ${MICRO_ROS_LIB_DIR}/include/" >&2
fi

LIB_SIZE="$(du -sh "${MICRO_ROS_LIB_DIR}/libmicroros.a" | cut -f1)"
INCLUDE_COUNT="$(find "${MICRO_ROS_LIB_DIR}/include" -name '*.h' 2>/dev/null | wc -l)"

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║  micro-ROS static library built successfully                     ║"
echo "╠═══════════════════════════════════════════════════════════════════╣"
printf "║  Library  : %-52s ║\n" "${MICRO_ROS_LIB_DIR}/libmicroros.a (${LIB_SIZE})"
printf "║  Headers  : %-52s ║\n" "${INCLUDE_COUNT} .h files in micro_ros_lib/include/"
echo "╠═══════════════════════════════════════════════════════════════════╣"
echo "║  Next — build the STM32 firmware:                                ║"
echo "║    cd firmware/stm32_chassis                                     ║"
echo "║    cmake -B build \\                                              ║"
echo "║      -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake \\       ║"
echo "║      -DSTM32_ENABLE_MICROROS=ON                                  ║"
echo "║    cmake --build build -j4                                       ║"
echo "║    # Flash: bash ../../scripts/flash_stm32.sh --build           ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
