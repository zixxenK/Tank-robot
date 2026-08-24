# STM32 Chassis Firmware

STM32F407VGT6 chassis controller firmware for the Rock64-based tank robot.

## Active Project
- **Authoritative CubeMX project**: `RosRobotControllerM4.ioc`
- **Historical factory reference**: `legacy_hiwonder_reference/RosRobotControllerM4.ioc`
- **Generated project name**: `RosRobotControllerM4`
- **Target**: STM32F407VGT6 (ARM Cortex-M4F)
- **Host transport**: onboard WCH USB-UART on product UART1 to USART1 on
  PA9/PA10
  at 1,000,000 baud

The legacy IOC is the original Hiwonder/7in1 hardware reference. CMake does
not parse or regenerate the IOC; it builds the checked-in production sources.
The reference is not a production host-port selector.

## Build
```bash
cd firmware/stm32_chassis
cmake --preset Debug
cmake --build --preset Debug --parallel 4
```

The production host link is fixed and requires no generated-code edits:

```powershell
..\..\scripts\stm32_port_profile.ps1 -HostUart USART1
```

Do not select USART3 for this robot. The stock 7in1 `USART3/PD8-PD9`
assignment is retained only in `legacy_hiwonder_reference/` for comparison.
Flash only through the Rock64 workflow documented in the repository root.

## Hardware Interface
- USB_OTG_HS is diagnostic-only and is not a motor transport
- USART1 (PA9/PA10, product UART1 USB-C) - Rock64 host communication at
  1,000,000 baud
- USART2 (PD5/PD6, `BLE_TX`/`BLE_RX`) is auxiliary/Bluetooth at 9,600 baud;
  USART3 (PD8/PD9, `MASTER_TX`/`MASTER_RX`) remains the separate factory pair.
- Packed binary protocol for motor commands and telemetry
