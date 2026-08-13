# Rock64 Ranger Firmware

STM32F407VGT6 chassis controller firmware for the Rock64-based tank robot.

## Active Project
- **Authoritative CubeMX configuration**: `RosRobotControllerM4factory.ioc`
- **Generated project name**: `RosRobotControllerM4`
- **Target**: STM32F407VGT6 (ARM Cortex-M4F)
- **Host transport**: `USB_OTG_HS` device-only CDC on PB14/PB15

The IOC is the hardware authority. CMake does not parse or regenerate the IOC;
it builds the checked-in CubeMX-generated sources that were produced from it.
Do not use `RosRobotControllerM4.ioc` or any alternate IOC as a source of
hardware settings.

## Build
```bash
cd firmware/stm32_chassis
cmake -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake -DCMAKE_BUILD_TYPE=Debug -B build
ninja -C build
```

## Hardware Interface
- USB CDC (`USB_OTG_HS` device-only, PB14/PB15) - Rock64 host communication
- USART1 (PA9/PA10) remains configured by the factory project but is not the
  Rock64 transport
- Packed binary protocol for motor commands and telemetry
