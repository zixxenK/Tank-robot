# ARM Cortex-M4 cross-compilation toolchain for STM32F407
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(TOOLCHAIN_PREFIX arm-none-eabi-)

# Fallback directly to your absolute toolchain bin path if not defined
if(NOT TOOLCHAIN_ROOT)
    set(TOOLCHAIN_ROOT "C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin")
endif()

find_program(CMAKE_C_COMPILER   ${TOOLCHAIN_PREFIX}gcc   HINTS ${TOOLCHAIN_ROOT} REQUIRED)
find_program(CMAKE_CXX_COMPILER ${TOOLCHAIN_PREFIX}g++   HINTS ${TOOLCHAIN_ROOT} REQUIRED)
find_program(CMAKE_ASM_COMPILER ${TOOLCHAIN_PREFIX}gcc   HINTS ${TOOLCHAIN_ROOT} REQUIRED)
find_program(CMAKE_OBJCOPY      ${TOOLCHAIN_PREFIX}objcopy HINTS ${TOOLCHAIN_ROOT} REQUIRED)
find_program(CMAKE_OBJDUMP      ${TOOLCHAIN_PREFIX}objdump HINTS ${TOOLCHAIN_ROOT} REQUIRED)
find_program(CMAKE_SIZE         ${TOOLCHAIN_PREFIX}size    HINTS ${TOOLCHAIN_ROOT} REQUIRED)

set(CMAKE_C_FLAGS_INIT   "-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard")
set(CMAKE_CXX_FLAGS_INIT "-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard")
set(CMAKE_ASM_FLAGS_INIT "-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard")

set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)