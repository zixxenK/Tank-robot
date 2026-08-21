# Rock64 Pi-2 Bus Pinout and Sensor Allocation

This chart is derived from the attached Rock64 Pi-2 bus image and the current
Tank-Robot 1.0 wiring contract.

## Production Rule

The STM32 motor controller is not driven from bare Rock64 GPIO pins. The
production motor-data path is:

```text
Rock64 USB host -> WCH USB-UART adapter -> /dev/rock64_stm32
                -> STM32 USART1 PA9/PA10 -> packed binary motor protocol
```

The ST-Link is programming/debug only and must be connected to the Rock64 for
firmware release workflows. Development PCs never flash the STM32 directly.

## Pi-2 Header Buses

| Physical pins | Rock64 signal | Bus role | Tank-Robot allocation |
|---|---|---|---|
| 1, 17 | 3.3V | Low-current logic power | Reference only; do not power 5V sensors from 3.3V |
| 2, 4 | 5V | Sensor power rail | Camera/auxiliary 5V sensors only within board power budget |
| 6, 9, 14, 20, 25, 30, 34, 39 | GND | Ground | Common ground for all header-attached sensors |
| 3 | GPIO2_D1 / I2C0_SDA | I2C0 data | Default I2C sensor SDA for future low-speed sensors |
| 5 | GPIO2_D0 / I2C0_SCL | I2C0 clock | Default I2C sensor SCL for future low-speed sensors |
| 8 | GPIO2_A0 / UART2_TX_M1 | UART2 TX | Direct Rock64 UART sensor TX, not STM32 motor control |
| 10 | GPIO2_A1 / UART2_RX_M1 | UART2 RX | Direct Rock64 UART sensor RX, not STM32 motor control |
| 12 | GPIO2_A3 | GPIO | STL-50B2 LiDAR sync input default (`/dev/gpiochip2`, offset 3) |
| 19 | GPIO3_A1 / SPI_TXD_M2 | SPI MOSI | Future SPI sensor MOSI |
| 21 | GPIO3_A2 / SPI_RXD_M2 | SPI MISO | Future SPI sensor MISO |
| 23 | GPIO3_A0 / SPI_CLK_M2 | SPI clock | Future SPI sensor SCLK |
| 24 | GPIO3_B0 / SPI_CSN0_M2 | SPI chip select 0 | Future SPI sensor CS0 |
| 26 | GPIO2_B4 / SPI_CSN1_M0 | SPI chip select 1 | Future SPI sensor CS1 |
| 27 | GPIO2_A4 / I2C1_SDA | I2C1 data / ID EEPROM | Reserved; use only for HAT/EEPROM-style devices |
| 28 | GPIO2_A5 / I2C1_SCL | I2C1 clock / ID EEPROM | Reserved; use only for HAT/EEPROM-style devices |

## Recommended Sensor Placement

| Sensor or module | Preferred connection | Rationale |
|---|---|---|
| STM32 motor controller | WCH USB-UART `/dev/rock64_stm32` | Preserves validated 1.0 packed-binary USART1 path |
| STM32 programming/debug | ST-Link on Rock64 USB only | Keeps firmware release, readback verification, and UART proof on robot host |
| STL-50B2 LiDAR | UART2 pins 8/10 plus sync GPIO pin 12 | Matches existing launch defaults and avoids sharing STM32 motor UART |
| I2C IMU/range add-ons | I2C0 pins 3/5 | Standard low-speed sensor bus on the Pi-2 header |
| SPI display/high-rate sensor | SPI pins 19/21/23/24/26 | Dedicated SPI pins from the attached pinout |
| USB camera | Rock64 USB/V4L2, auto-resolved by launch | Avoids consuming Pi-2 GPIO pins |
| ESP32 camera | Wi-Fi stream configured by `CAMERA_IP_STATION` | Existing bridge consumes network video, not header GPIO |

## Electrical Notes

- Header GPIO is 3.3V logic. Do not feed 5V signal outputs directly into a
  Rock64 GPIO input without level shifting.
- The STM32/YX4055 motor-side logic is 0-5V and is isolated from the Rock64
  header by the validated WCH USB-UART path.
- The JGB3865-520R45-12-150RPM motors remain controlled by STM32 firmware and
  the hardened ROS bridge. Rock64 ROS nodes send velocity setpoints, not raw
  PWM or current commands.
