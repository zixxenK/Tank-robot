# Hiwonder Glowy ultrasonic sensor build path

This is the production distance-sensor path for the Hiwonder Glowy RGB
ultrasonic module. The module is an I2C peripheral and plugs into the
Hiwonder controller's dedicated four-pin I2C connector.

## Hardware

Use the controller's blue four-position peripheral connector labeled:

| Module wire | Controller label |
|---|---|
| VCC | 5V |
| GND | GND |
| SDA | SDA |
| SCL | SCL |

Do not connect this module to the legacy PWM pads or to Rock64 GPIO. The
controller firmware shares I2C2 between the project's QMI8658 runtime path and
this module (Hiwonder's live hardware pages call the onboard part MPU6050):
PB10 is SCL and PB11 is SDA. The module uses 7-bit I2C address `0x77`.

The official module specification is 5 V, 2–400 cm, 40 kHz, 15° field of
view, and a four-pin interface. Use the matching Hiwonder four-wire lead and
the controller's labeled connector; do not infer pin order from wire colors.

## Firmware and ROS path

```text
Glowy module -> controller I2C2 PB10/PB11 -> STM32 -> USART1 -> Rock64
              -> stm32_hardened_bridge -> /ultrasonic/range
```

The STM32 reads register `0x00` as a little-endian unsigned distance in
millimetres. Values from 20 through 4000 mm are valid. The RGB registers are
owned by the module and are not required for distance acquisition.

The ROS API remains `/ultrasonic/range` (`sensor_msgs/Range`) so existing
navigation and visualization consumers do not need to change. Diagnostics are
published on `/stm32/diagnostics` as `Hiwonder Glowy` with read, valid, and
I2C-error counters.

## Test

With the robot stationary and motor power disabled:

```bash
source /opt/rock64-robot/deployment/scripts/source_host_ws.sh
ros2 topic echo /ultrasonic/range
ros2 topic echo /stm32/diagnostics
```

A connected sensor produces finite values on `/ultrasonic/range`; the
diagnostic `read_count` and `valid_count` increase. If `error_count` rises,
check the four-pin connector, 5 V/GND, SDA/SCL order, and I2C bus pull-ups.

The Rock64 deployment script builds and flashes the STM32 image before the
sensor is tested:

```bash
cd /opt/rock64-robot
bash deployment/scripts/rock64_update_and_flash.sh
```
