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
set(CMAKE_PROJECT_NAME factoryfirmwarestm32)

# Enable compile command to ease indexing with e.g. clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Core project settings
project(${CMAKE_PROJECT_NAME})
message("Build type: " ${CMAKE_BUILD_TYPE})

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

# Add linker script
target_link_options(${CMAKE_PROJECT_NAME} PRIVATE
    -T${CMAKE_CURRENT_SOURCE_DIR}/STM32F407xx_FLASH.ld
)

# Add Hiwonder sources (minimal set for basic tank functionality)
# Motor control and encoders
file(GLOB_RECURSE MOTOR_SOURCES
    "Hiwonder/Peripherals/encoder_motor.c"
    "Hiwonder/Portings/motor_porting.c"
    "Hiwonder/Misc/pid.c"
)

# Memory management (lwmem)
file(GLOB_RECURSE LWMEM_SOURCES
    "Hiwonder/Portings/lwmem_porting.c"
    "Third_Party/Lw/*.c"
)

# Binary protocol integration (UART communication)
file(GLOB_RECURSE BINARY_PROTOCOL_SOURCES
    "Hiwonder/System/uart_binary_protocol_packed.c"
    "Hiwonder/System/uart_binary_protocol_integration_packed.c"
)

# Motor control wrapper layer
file(GLOB_RECURSE MOTOR_CONTROL_SOURCES
    "Hiwonder/System/motor_control.c"
)

# IMU integration (with fixed delta time)
file(GLOB_RECURSE IMU_SOURCES
    "Hiwonder/Peripherals/imu.c"
    "Hiwonder/Peripherals/imu_mpu6050.c"
    "Hiwonder/Portings/imu_porting.c"
    "Hiwonder/System/imu_integration.c"
)

# Battery/ADC integration (with filter priming)
file(GLOB_RECURSE BATTERY_SOURCES
    "Hiwonder/System/battery_integration.c"
    "Hiwonder/System/battery_handle.c"
)

# Status peripherals (buzzer/LED)
file(GLOB_RECURSE STATUS_SOURCES
    "Hiwonder/Peripherals/buzzer.c"
    "Hiwonder/Portings/buzzer_porting.c"
    "Hiwonder/Peripherals/led.c"
    "Hiwonder/Portings/led_porting.c"
    "Hiwonder/System/status_integration.c"
)

# Third-party Fusion library for IMU sensor fusion
file(GLOB_RECURSE FUSION_SOURCES "Third_Party/Fusion/Fusion/*.c")

# ============================================================================
# BLOAT QUARANTINE (Explicitly excluded from build)
# ============================================================================
# These files are deliberately excluded to free CPU/RAM and prevent
# conflicting control sources. The ROCK64 is now the sole master.

# EXCLUDED: Wireless parsers (SBUS, Bluetooth)
# "Hiwonder/Misc/sbus.c"
# "Hiwonder/Portings/sbus_porting.c"
# "Hiwonder/Portings/bluetooth_porting.c"

# EXCLUDED: Legacy kinematics (chassis control)
# "Hiwonder/Chassis/chassis.c"
# "Hiwonder/Chassis/differential_chassis.c"
# "Hiwonder/Chassis/mecanum_chassis.c"
# "Hiwonder/Chassis/ackermann_chassis.c"
# "Hiwonder/Portings/chassis_porting.c"

# EXCLUDED: LVGL UI framework
# "Hiwonder/LVGL_UI/*.c"

# Add micro-ROS integration sources (if micro-ROS is enabled)
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/micro_ros_lib/libmicroros.a")
    file(GLOB MICROROS_SOURCES
        "Core/Src/microros_transport.c"
        "Core/Src/microros_node.c"
    )
    message("Adding micro-ROS integration sources")
endif()

# Add micro-ROS library (if built)
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/micro_ros_lib/libmicroros.a")
    message("Found micro-ROS static library")
    target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
        micro_ros_lib/include
    )
    target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/micro_ros_lib/libmicroros.a
    )
    target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE
        MICROROS_ENABLED
    )
endif()

# Add third-party library sources (minimal set)
# file(GLOB_RECURSE FUSION_SOURCES "Third_Party/Fusion/Fusion/*.c")

# Add sources to executable
target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    ${MOTOR_SOURCES}
    ${LWMEM_SOURCES}
    ${BINARY_PROTOCOL_SOURCES}
    ${MOTOR_CONTROL_SOURCES}
    ${IMU_SOURCES}
    ${BATTERY_SOURCES}
    ${STATUS_SOURCES}
    ${FUSION_SOURCES}
    ${MICROROS_SOURCES}
)

# Add include paths
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Hiwonder include paths (minimal set for integration)
    Hiwonder/Peripherals
    Hiwonder/Portings
    Hiwonder/System
    Hiwonder/Misc
    Hiwonder/USB_HOST
    Hiwonder/Chassis
    # Third-party library include paths
    Third_Party/Fusion
    Third_Party/Fusion/Fusion
    Third_Party/RTT
    Third_Party/Lw
    # Core HAL includes
    Core/Inc
)

# Add project symbols (macros)
target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined symbols
)

# Remove wrong libob.a library dependency when using cpp files
list(REMOVE_ITEM CMAKE_C_IMPLICIT_LINK_LIBRARIES ob)

# Add linked libraries
target_link_libraries(${CMAKE_PROJECT_NAME}
    stm32cubemx
    m

    # Add user defined libraries
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
