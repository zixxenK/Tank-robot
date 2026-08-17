# Rock64 Ranger Firmware

STM32F407VGT6 chassis controller firmware for the Rock64-based tank robot.

## Active Project
- **Authoritative hardware reference**: `legacy_hiwonder_reference/RosRobotControllerM4.ioc`
- **Generated project name**: `RosRobotControllerM4`
- **Target**: STM32F407VGT6 (ARM Cortex-M4F)
- **Host transport**: onboard WCH USB-UART on product UART1 to USART1 on
  PA9/PA10
  at 1,000,000 baud

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

The host-link profile is selectable without editing generated UART code. The
default is the approved custom UART1 connector mapping:

```powershell
..\..\scripts\stm32_port_profile.ps1 -HostUart USART1
```

For a board physically wired like the stock 7in1 reference, select USART3:

```powershell
..\..\scripts\stm32_port_profile.ps1 -HostUart USART3
```

This changes the firmware endpoint only; it cannot rewire the PCB. Flash the
selected Release image only after confirming the physical connector traces:
`..\..\scripts\stm32_port_profile.ps1 -HostUart USART1 -Flash`.

## Hardware Interface
- USB_OTG_HS is diagnostic-only and is not a motor transport
- USART1 (PA9/PA10, product UART1 USB-C) - Rock64 host communication at
  1,000,000 baud
- USART2 (PD5/PD6, `BLE_TX`/`BLE_RX`) is auxiliary/Bluetooth at 9,600 baud;
  USART3 (PD8/PD9, `MASTER_TX`/`MASTER_RX`) remains the separate factory pair.
- Packed binary protocol for motor commands and telemetry
