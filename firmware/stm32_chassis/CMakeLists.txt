cmake_minimum_required(VERSION 3.22)

#
# This file is generated only once,
# and is not re-generated if converter is called multiple times.
#
# User is free to modify the file as much as necessary
#

# Setup compiler settings
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)


# Define the build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug")
endif()

# Set the project name
set(CMAKE_PROJECT_NAME RosRobotControllerM4)

# Enable compile command to ease indexing with e.g. clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Core project settings
project(${CMAKE_PROJECT_NAME})
message("Build type: " ${CMAKE_BUILD_TYPE})

# Production host link is fixed: physical UART1 -> USART1 on PA9/PA10.
# The stock USART3/PD8-PD9 endpoint is reference material only and is not a
# selectable production build profile.

# Enable CMake support for ASM and C languages
enable_language(C ASM)

# Create an executable object type
add_executable(${CMAKE_PROJECT_NAME})

# Add STM32CubeMX generated sources
add_subdirectory(cmake/stm32cubemx)

# Link directories setup
target_link_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined library search paths
)

target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    Hiwonder/Peripherals/encoder_motor.c
    Hiwonder/Peripherals/imu_mpu6050.c
    Hiwonder/Peripherals/buzzer.c
    Hiwonder/Peripherals/led.c
    Hiwonder/Peripherals/serial_servo.c
    Hiwonder/Portings/motor_porting.c
    Hiwonder/Portings/buzzer_porting.c
    Hiwonder/Portings/lwmem_porting.c
    Hiwonder/Misc/pid.c
    Hiwonder/System/motor_control.c
    Hiwonder/System/uart_binary_protocol_packed.c
    Hiwonder/System/uart_binary_protocol_integration_packed.c
    Hiwonder/System/watchdog.c
    Hiwonder/System/imu_integration.c
    Hiwonder/System/battery_integration.c
    Hiwonder/System/status_integration.c
    Hiwonder/System/hc_sr04.c
    Third_Party/Fusion/Fusion/FusionAhrs.c
    Third_Party/Fusion/Fusion/FusionCompass.c
    Third_Party/Fusion/Fusion/FusionOffset.c
    Third_Party/Lw/lwmem.c
    Third_Party/Lw/lwmem_sys_cmsis_os.c
)

# Add include paths
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Hiwonder include paths (minimal set for integration)
    Hiwonder/Peripherals
    Hiwonder/Portings
    Hiwonder/System
    Hiwonder/Misc
    Third_Party/Lw
    # Third-party library include paths
    Third_Party/Fusion
    Third_Party/Fusion/Fusion
    # Core HAL includes
    Core/Inc
)

# Remove wrong libob.a library dependency when using cpp files
list(REMOVE_ITEM CMAKE_C_IMPLICIT_LINK_LIBRARIES ob)

# Add linked libraries
target_link_libraries(${CMAKE_PROJECT_NAME}
    stm32cubemx
    m

    # Add user defined libraries
)

# Add linker script for STM32F407
target_link_options(${CMAKE_PROJECT_NAME} PRIVATE
    -T${CMAKE_CURRENT_SOURCE_DIR}/Core/STM32F407VGTx_FLASH.ld
    -Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.map
)

# Post-build: generate flash images
add_custom_command(TARGET ${CMAKE_PROJECT_NAME} POST_BUILD
    COMMAND arm-none-eabi-objcopy -O binary
        $<TARGET_FILE:${CMAKE_PROJECT_NAME}>
        ${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.bin
    COMMAND arm-none-eabi-objcopy -O ihex
        $<TARGET_FILE:${CMAKE_PROJECT_NAME}>
        ${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.hex
    COMMENT "Generating .bin and .hex flash images"
)

# Add flash target using OpenOCD (most reliable)
set(OPENOCD_TRANSPORT "hla_swd" CACHE STRING
    "OpenOCD ST-Link transport (Rock64=hla_swd, newer desktop=swd)")
add_custom_target(flash
    COMMAND openocd -f interface/stlink.cfg
        -c "transport select ${OPENOCD_TRANSPORT}"
        -f target/stm32f4x.cfg
        -c "program ${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.bin 0x08000000 verify reset exit"
    DEPENDS ${CMAKE_PROJECT_NAME}
    COMMENT "Flashing firmware to STM32 via OpenOCD"
)
