cmake_minimum_required(VERSION 3.16)

# Cross-compilation guard - the STM32 toolchain file must be supplied explicitly.
if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
  message(FATAL_ERROR
    "This project must be cross-compiled for STM32. "
    "Pass -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake")
endif()

project(rock64_ranger_stm32 C CXX ASM)

if(CMAKE_C_COMPILER_ID STREQUAL "MSVC")
  message(FATAL_ERROR
    "MSVC/Visual Studio is not supported for STM32 firmware cross-compilation. "
    "Configure with ARM GCC toolchain instead, for example:\n"
    "  cmake -S . -B build -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake\n"
    "  cmake --build build")
endif()

option(STM32_ENABLE_MICROROS "Enable micro-ROS control path" ON)

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
set(MICROROS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/micro_ros_lib")
set(MICROROS_LIB "${MICROROS_DIR}/libmicroros.a")

if(NOT EXISTS "${STM32_HAL_DIR}/Src/stm32f4xx_hal.c")
  message(FATAL_ERROR
    "Missing STM32 HAL drivers. Populate firmware/stm32_chassis/Drivers first. "
    "Use scripts/sync_stm32_drivers.sh to fetch STM32CubeF4 Drivers/. ")
endif()

if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/Core/Src/system_stm32f4xx.c" AND NOT EXISTS "${STM32_CMSIS_DIR}/Device/ST/STM32F4xx/Source/Templates/system_stm32f4xx.c")
  message(FATAL_ERROR
    "Missing system_stm32f4xx.c in Core/Src or Drivers/CMSIS.")
endif()

set(HAL_SOURCES
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_adc.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_adc_ex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_crc.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_cortex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_dma.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_flash.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_flash_ex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_gpio.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_i2c.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_iwdg.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_pwr.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_pwr_ex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_rcc.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_rcc_ex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_spi.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_tim.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_tim_ex.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_uart.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_hal_hcd.c
  ${STM32_HAL_DIR}/Src/stm32f4xx_ll_usb.c
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

file(GLOB HIWONDER_SOURCES
  "Hiwonder/Chassis/*.c"
  "Hiwonder/LVGL_UI/*.c"
  "Hiwonder/LVGL_UI/guider_fonts/*.c"
  "Hiwonder/LVGL_UI/images/*.c"
  "Hiwonder/Misc/*.c"
  "Hiwonder/Peripherals/*.c"
  "Hiwonder/Portings/*.c"
  "Hiwonder/System/*.c"
  "Hiwonder/USB_HOST/*.c"
)

# Legacy duplicate of GUI task implementation; System/gui_handle.c is the active variant.
list(REMOVE_ITEM HIWONDER_SOURCES
  ${CMAKE_CURRENT_SOURCE_DIR}/Hiwonder/LVGL_UI/lvgl_handle.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Hiwonder/System/checksum.c
)

file(GLOB_RECURSE LVGL_SOURCES
  "Third_Party/LVGL/src/*.c"
  "Third_Party/LVGL/porting/*.c"
)

file(GLOB U8G2_SOURCES
  "Third_Party/U8g2/*.c"
)

set(LW_SOURCES
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Lw/lwmem.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Lw/lwmem_sys_cmsis_os.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Lw/lwpkt.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Lw/lwrb.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Lw/lwshell.c
)

set(RTOS_ADAPTER_SOURCES
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/CMSIS_RTOS_V2/cmsis_os2.c
)

set(FREERTOS_SOURCES
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/croutine.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/event_groups.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/list.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/queue.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/stream_buffer.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/tasks.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/timers.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/portable/GCC/ARM_CM4F/port.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/portable/MemMang/heap_4.c
)

set(FUSION_SOURCES
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Fusion/Fusion/FusionAhrs.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Fusion/Fusion/FusionCompass.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Fusion/Fusion/FusionOffset.c
)

set(USB_HOST_SOURCES
  ${CMAKE_CURRENT_SOURCE_DIR}/USB_HOST/App/usb_host.c
  ${CMAKE_CURRENT_SOURCE_DIR}/USB_HOST/Target/usbh_conf.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Core/Src/usbh_core.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Core/Src/usbh_ctlreq.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Core/Src/usbh_ioreq.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Core/Src/usbh_pipes.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Class/HID/Src/usbh_hid.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Class/HID/Src/usbh_hid_keybd.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Class/HID/Src/usbh_hid_mouse.c
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Class/HID/Src/usbh_hid_parser.c
)

# ── Firmware executable ────────────────────────────────────────────────────
add_executable(rock64_ranger_fw
  ${FIRMWARE_SOURCES}
  ${HIWONDER_SOURCES}
  ${LVGL_SOURCES}
  ${U8G2_SOURCES}
  ${LW_SOURCES}
  ${RTOS_ADAPTER_SOURCES}
  ${FREERTOS_SOURCES}
  ${FUSION_SOURCES}
  ${USB_HOST_SOURCES}
  ${HAL_SOURCES}
)

set_target_properties(rock64_ranger_fw PROPERTIES SUFFIX ".elf")

target_include_directories(rock64_ranger_fw PRIVATE
  Core/Inc
  Hiwonder/System
  ${STM32_HAL_DIR}/Inc
  ${STM32_CMSIS_DIR}/Device/ST/STM32F4xx/Include
  ${STM32_CMSIS_DIR}/Include
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/include
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/CMSIS_RTOS_V2
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/Third_Party/FreeRTOS/Source/portable/GCC/ARM_CM4F
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/RTT
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/U8g2
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Lw
  ${CMAKE_CURRENT_SOURCE_DIR}/Third_Party/Fusion/Fusion
  ${CMAKE_CURRENT_SOURCE_DIR}/Hiwonder/Peripherals
  ${CMAKE_CURRENT_SOURCE_DIR}/Hiwonder/Misc
  ${CMAKE_CURRENT_SOURCE_DIR}/Hiwonder/Chassis
  ${CMAKE_CURRENT_SOURCE_DIR}/Hiwonder/Portings
  ${CMAKE_CURRENT_SOURCE_DIR}/Hiwonder/USB_HOST
  ${CMAKE_CURRENT_SOURCE_DIR}/USB_HOST/App
  ${CMAKE_CURRENT_SOURCE_DIR}/USB_HOST/Target
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Core/Inc
  ${CMAKE_CURRENT_SOURCE_DIR}/Middlewares/ST/STM32_USB_Host_Library/Class/HID/Inc
)

# Disable micro-ROS since we're using legacy bridges
set(STM32_ENABLE_MICROROS OFF CACHE BOOL "Enable micro-ROS support" FORCE)

if(STM32_ENABLE_MICROROS)
  if(NOT EXISTS "${MICROROS_LIB}")
    message(FATAL_ERROR
      "STM32_ENABLE_MICROROS is ON but ${MICROROS_LIB} is missing.\n"
      "Build the micro-ROS static library first:\n"
      "  bash scripts/build_microros.sh\n"
      "Then re-run CMake.  See firmware/stm32_chassis/micro_ros_lib/README.txt.")
  endif()

  if(NOT IS_DIRECTORY "${MICROROS_DIR}/include")
    message(FATAL_ERROR
      "micro_ros_lib/include/ not found.  Re-run scripts/build_microros.sh "
      "to regenerate the library and headers together.")
  endif()

  target_include_directories(rock64_ranger_fw PRIVATE
    ${MICROROS_DIR}/include
  )

  target_compile_definitions(rock64_ranger_fw PRIVATE
    STM32_ENABLE_MICROROS
  )
endif()

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

if(STM32_ENABLE_MICROROS)
  # Force link micro-ROS and standard system libraries without looking for an external libatomic file
  target_link_libraries(rock64_ranger_fw PRIVATE ${MICROROS_LIB} m c nosys)
else()
  target_link_libraries(rock64_ranger_fw PRIVATE m c nosys)
endif()

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
