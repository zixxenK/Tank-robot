cmake_minimum_required(VERSION 3.16)

# Cross-compilation guard - the STM32 toolchain file must be supplied explicitly.
if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
  message(FATAL_ERROR
    "This project must be cross-compiled for STM32. "
    "Pass -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake")
endif()

project(rock64_ranger_stm32 C CXX ASM)

# Using plain-UART communication instead of micro-ROS for STM32
# This simplifies the firmware and reduces memory requirements
# If micro-ROS is needed in the future, enable STM32_ENABLE_MICROROS option

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

# ── Firmware executable ────────────────────────────────────────────────────
add_executable(rock64_ranger_fw ${FIRMWARE_SOURCES})

target_include_directories(rock64_ranger_fw PRIVATE
  Core/Inc
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

target_link_libraries(rock64_ranger_fw PRIVATE m c nosys)

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
