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

# ── STM32CubeF4 Drivers root (local checkout, not fetched by CMake) ──────
set(STM32_DRIVERS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/Drivers")
set(STM32_HAL_DIR "${STM32_DRIVERS_DIR}/STM32F4xx_HAL_Driver")
set(STM32_CMSIS_DIR "${STM32_DRIVERS_DIR}/CMSIS")

if(NOT EXISTS "${STM32_HAL_DIR}/Src/stm32f4xx_hal.c")
  message(FATAL_ERROR
    "Missing STM32 HAL drivers. Populate firmware/stm32_chassis/Drivers first. "
    "Use scripts/sync_stm32_drivers.sh to fetch STM32CubeF4 Drivers/. ")
endif()

if(NOT EXISTS "${STM32_CMSIS_DIR}/Device/ST/STM32F4xx/Source/Templates/system_stm32f4xx.c")
  message(FATAL_ERROR
    "Missing STM32 CMSIS device files in firmware/stm32_chassis/Drivers/CMSIS. "
    "Sync STM32CubeF4 Drivers/CMSIS with scripts/sync_stm32_drivers.sh.")
endif()

set(HAL_SOURCES
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_cortex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_dma.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_flash.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_flash_ex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_gpio.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_i2c.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_pwr.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_pwr_ex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_rcc.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_rcc_ex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_tim.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_tim_ex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_uart.c
)

set(CMSIS_SOURCES
  ${STM32_CMSIS_DIR}/Device/ST/STM32F4xx/Source/Templates/system_stm32f4xx.c
)

# ── Source files ───────────────────────────────────────────────────────────
file(GLOB_RECURSE FIRMWARE_SOURCES
  "Core/Src/*.c"
  "Core/Src/*.cpp"
  "Core/Startup/*.s"
)

# ── Firmware executable ────────────────────────────────────────────────────
add_executable(rock64_ranger_fw
  ${FIRMWARE_SOURCES}
  ${HAL_SOURCES}
  ${CMSIS_SOURCES}
)

target_include_directories(rock64_ranger_fw PRIVATE
  Core/Inc
  ${STM32_HAL_DIR}/Inc
  ${STM32_CMSIS_DIR}/Device/ST/STM32F4xx/Include
  ${STM32_CMSIS_DIR}/Include
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
