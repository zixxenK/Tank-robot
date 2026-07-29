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

# Add Hiwonder sources (minimal set for basic tank functionality)
# file(GLOB_RECURSE HIWONDER_SOURCES
#     "Hiwonder/Chassis/*.c"
#     "Hiwonder/Peripherals/encoder_motor.c"
#     "Hiwonder/Peripherals/pwm_servo.c"
#     "Hiwonder/Misc/pid.c"
# )

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
    # ${HIWONDER_SOURCES}
    # ${FUSION_SOURCES}
    ${MICROROS_SOURCES}
)

# Add include paths
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add Hiwonder include paths (minimal)
    # Hiwonder/Chassis
    # Hiwonder/System
    # Hiwonder/Peripherals
    # Hiwonder/Misc
    # Add minimal third-party library include paths
    # Third_Party/Fusion
    # Third_Party/Fusion/Fusion
    # Add micro-ROS include paths (if enabled)
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
