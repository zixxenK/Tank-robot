cmake_minimum_required(VERSION 3.16)

# Cross-compilation guard - must be set before project()
if(NOT CMAKE_CROSSCOMPILING)
  message(FATAL_ERROR
    "This project must be cross-compiled for STM32. "
    "Pass -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake")
endif()

project(rock64_ranger_stm32 C CXX ASM)

# ── MCU / Cortex-M4 flags ──────────────────────────────────────────────────
set(MCU_FLAGS
  -mcpu=cortex-m4
  -mthumb
  -mfpu=fpv4-sp-d16
  -mfloat-abi=hard
)

# ── Source files ───────────────────────────────────────────────────────────
file(GLOB_RECURSE FIRMWARE_SOURCES
  "Core/Src/*.c"
  "Core/Src/*.cpp"
  "Core/Startup/*.s"
)

# ── micro-ROS static library ───────────────────────────────────────────────
set(MICROROS_LIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/micro_ros_lib")
set(MICROROS_STATIC_LIB "${MICROROS_LIB_DIR}/libmicroros.a")
set(MICROROS_INCLUDE_DIR "${MICROROS_LIB_DIR}/include")

if(NOT EXISTS "${MICROROS_STATIC_LIB}")
  message(WARNING
    "libmicroros.a not found at ${MICROROS_STATIC_LIB}. "
    "Run scripts/build_microros.sh to generate it.")
endif()

add_library(microros STATIC IMPORTED)
set_target_properties(microros PROPERTIES
  IMPORTED_LOCATION "${MICROROS_STATIC_LIB}"
  INTERFACE_INCLUDE_DIRECTORIES "${MICROROS_INCLUDE_DIR}"
)

# ── Firmware executable ────────────────────────────────────────────────────
add_executable(rock64_ranger_fw ${FIRMWARE_SOURCES})

target_include_directories(rock64_ranger_fw PRIVATE
  Core/Inc
  Core/Inc/motors
  ${MICROROS_INCLUDE_DIR}
)

target_compile_definitions(rock64_ranger_fw PRIVATE
  USE_HAL_DRIVER
  STM32F407xx
)

target_compile_options(rock64_ranger_fw PRIVATE
  ${MCU_FLAGS}
  -Wall
  -Wextra
  -fdata-sections
  -ffunction-sections
  -fno-exceptions
  "$<$<CONFIG:Debug>:-Og;-g3>"
  "$<$<CONFIG:Release>:-O2>"
)

target_link_options(rock64_ranger_fw PRIVATE
  ${MCU_FLAGS}
  -T${CMAKE_CURRENT_SOURCE_DIR}/Core/STM32F407VGTx_FLASH.ld
  -Wl,--gc-sections
  -Wl,--print-memory-usage
  -specs=nosys.specs
  -specs=nano.specs
)

# ── Link against micro-ROS ─────────────────────────────────────────────────
target_link_libraries(rock64_ranger_fw PRIVATE microros m c nosys)

# ── Post-build: generate flash images ─────────────────────────────────────
add_custom_command(TARGET rock64_ranger_fw POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O binary
    $<TARGET_FILE:rock64_ranger_fw>
    ${CMAKE_CURRENT_BINARY_DIR}/rock64_ranger_fw.bin
  COMMAND ${CMAKE_OBJCOPY} -O ihex
    $<TARGET_FILE:rock64_ranger_fw>
    ${CMAKE_CURRENT_BINARY_DIR}/rock64_ranger_fw.hex
  COMMENT "Generating .bin and .hex flash images"
)
