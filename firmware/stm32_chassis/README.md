# Rock64 Ranger Firmware

STM32F407VGT6 chassis controller firmware for the Rock64-based tank robot.

## Active Project
- **CubeMX Project**: `rock64_ranger_fw.ioc`
- **Project Name**: rock64_ranger_fw
- **Target**: STM32F407VGT6 (ARM Cortex-M4F)

## Legacy Reference
Original Hiwonder factory project is preserved in `legacy_hiwonder_reference/` for fallback purposes.
DO NOT use `RosRobotControllerM4.ioc` for active development.

## Build
```bash
cd firmware/stm32_chassis
cmake -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake -DCMAKE_BUILD_TYPE=Debug -B build
ninja -C build
```

## Hardware Interface
- USART1 (PA9/PA10) @ 115200 baud - Rock64 host communication
- DMA circular buffer for USART1 RX/TX
- Packed binary protocol for motor commands and telemetry
