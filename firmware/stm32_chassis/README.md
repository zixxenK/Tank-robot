# Rock64 Ranger Firmware

STM32F407VGT6 chassis controller firmware for the Rock64-based tank robot.

## Active Project
- **Authoritative hardware reference**: `legacy_hiwonder_reference/RosRobotControllerM4.ioc`
- **Generated project name**: `RosRobotControllerM4`
- **Target**: STM32F407VGT6 (ARM Cortex-M4F)
- **Host transport**: onboard WCH USB-UART to USART2 on PD5/PD6 at 1,000,000 baud

The legacy IOC is the original Hiwonder hardware configuration. CMake does not
parse or regenerate the IOC; it builds the checked-in sources. Do not treat the
experimental `RosRobotControllerM4factory.ioc` CDC variant as the board
transport configuration.

## Build
```bash
cd firmware/stm32_chassis
cmake -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake -DCMAKE_BUILD_TYPE=Debug -B build
ninja -C build
```

## Hardware Interface
- USB_OTG_HS is diagnostic-only and is not a motor transport
- USART2 (PD5/PD6, factory `BLE_TX`/`BLE_RX` pins) - Rock64 host communication
  at 1,000,000 baud; USART3 is auxiliary/Bluetooth.
- Packed binary protocol for motor commands and telemetry
