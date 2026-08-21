# Rock64 to STM32 Packed Protocol

The validated physical transport assignment is defined by
[`SOURCE_OF_TRUTH_1_0.md`](SOURCE_OF_TRUTH_1_0.md).

## Physical Link

- Peripheral: WCH USB-UART bridge on the product-labeled UART1 connector to
  STM32 USART1
- Pins: PA9 UART1 TX/Rock64 RX, PA10 UART1 RX/Rock64 TX
- Host device: WCH `1a86:55d4`, normally exposed by Linux as `/dev/ttyACM*` and
  addressed through `/dev/rock64_stm32`.
- Line coding: 1,000,000 baud, 8 data bits, no parity, 1 stop bit
- RX: USART1 circular DMA; TX: bounded blocking UART writes

## Frame

```text
AA 55 FUNC LENGTH PAYLOAD... CRC
```

| Field | Bytes | Meaning |
| --- | ---: | --- |
| Sync | 2 | `0xAA 0x55` |
| Function | 1 | Message type |
| Length | 1 | Payload bytes, maximum 251 |
| Payload | 0-251 | Function-specific little-endian data |
| CRC | 1 | Reflected CRC-8/MAXIM table, initial value `0x00` |

CRC covers `FUNC`, `LENGTH`, and `PAYLOAD`. The historical function name
`crc8_ccitt` remains in host tests for compatibility, but the deployed table is
the reflected CRC-8/MAXIM table (`table[1] == 0x5E`).

## Function Codes

| Code | Name | Payload |
| ---: | --- | --- |
| `0x03` | Motor | Motor subcommand |
| `0x04` | Buzzer | `01 FREQUENCY_UINT16_LE` (`0` = off) |
| `0x05` | SG90 servo command/ack | `01 00 PULSE_US_UINT16_LE DURATION_MS_UINT16_LE` |
| `0x10` | Encoder | `<ii` left/right counts |
| `0x11` | Battery | `<ff` voltage/current |
| `0x12` | IMU | `<ffffff` acceleration/gyro |
| `0x13` | Legacy self-test | Reserved; use the Rock64 hardware acceptance runner |
| `0x14` | HC-SR04 | `<HHBB` distance mm, echo us, valid, reserved |
| `0xF0` | Heartbeat | Empty |
| `0xF1` | Acknowledgement | Implementation-defined |
| `0xFF` | Error | Error code |

## Motor Commands

Set speed payload:

```text
01 COUNT (MOTOR_ID FLOAT32_RPS) * COUNT
```

Rules enforced before accepting any entry:

- Exact payload length is `2 + COUNT * 5`.
- `COUNT` is 1 through 4.
- Motor IDs are 0 through 3 and unique within the frame.
- RPS values are finite IEEE-754 float32 values in `[-1.0, 1.0]`.
- A malformed command is rejected atomically.

Emergency stop payload:

```text
02 00
```

This is a deliberate custom-runtime semantic. In the stock Hiwonder 7in1
firmware, motor subcommand `0x02` is a single-motor stop and the second byte
is the motor ID; the stock all-motor stop is subcommand `0x03` with a motor
mask. Therefore the custom `02 00` frame must not be used as a stop-frame
compatibility test against the unmodified 7in1 image.

## Buzzer Commands

Set or clear the physical PA8 buzzer through the same UART1 link:

```text
01 FREQUENCY_UINT16_LE
```

The valid frequency range is 0 through 20,000 Hz. The Rock64 publishes these
commands on `/buzzer/frequency` as `std_msgs/Int32`; the hardened bridge is the
only node that writes them to the STM32 serial port. The STM32 image must be
rebuilt and flashed with the buzzer protocol extension for this topic to make
physical sound.

## SG90 Servo Commands

The production image controls one PWM servo only: channel `0`, board header
J1, STM32 PA11. PC8/PA12 are reserved for HC-SR04 TRIG/ECHO and are never
driven by the servo implementation.

```text
01 00 PULSE_US_UINT16_LE DURATION_MS_UINT16_LE
```

The firmware accepts 1,000 through 2,000 microseconds and 20 through 5,000
milliseconds. PA11 stays low until the first valid command. An accepted command
is echoed as a `0x05` frame; rejected commands produce no state update. The
Rock64 interface is `/stm32/servo/command_degrees` (`std_msgs/Float32`), with
acknowledged state on `/stm32/servo/state_degrees` and
`/stm32/servo/state_us` (`std_msgs/UInt16`). Normal host limits are 30 through
150 degrees.

## Timeouts and Rearming

- A valid motor-speed frame refreshes the command timestamp.
- Heartbeat frames are reserved and ignored by the motor-only runtime.
- A command timeout invokes immediate PWM/PID shutdown.
- The host bridge sends an emergency stop after every connect/reconnect.
- Motion is armed only after the serial port is open and a fresh safe velocity
  command has arrived.

## ROS Topics

| Topic | Type | Producer | Consumer |
| --- | --- | --- | --- |
| `/cmd_vel` | `geometry_msgs/Twist` | Teleop | Safety gateway |
| `/agent/cmd_vel_proposed` | `geometry_msgs/Twist` | Agent | Safety gateway |
| `/agent/heartbeat` | `std_msgs/Bool` | Agent | Safety gateway |
| `/safety/e_stop` | `std_msgs/Bool` | Operator/test runner | Safety gateway and hardened bridge |
| `/ranger/cmd_vel_safe` | `geometry_msgs/Twist` | Safety gateway | Hardened bridge |
| `/stm32/battery` | `sensor_msgs/BatteryState` | Hardened bridge | Safety gateway |
| `/stm32/encoder_ticks` | `std_msgs/Int32MultiArray` | Hardened bridge | Diagnostics |
| `/stm32/imu` | `sensor_msgs/Imu` | Hardened bridge | Consumers |
| `/ultrasonic/range` | `sensor_msgs/Range` | Hardened bridge | Consumers/test runner |
| `/stm32/servo/command_degrees` | `std_msgs/Float32` | Operator/test runner | Hardened bridge |
| `/stm32/servo/state_degrees` | `std_msgs/UInt16` | Hardened bridge | Operator/test runner |
| `/joy` | `sensor_msgs/Joy` | PS5 bridge | Buzzer/song controls |
| `/buzzer/frequency` | `std_msgs/Int32` | Song creator | Hardened STM32 bridge |
| `/buzzer/status` | `std_msgs/String` | Song creator | Operator/diagnostics |

For raised-track commissioning, the bridge additionally provides
`/stm32/motor_1/enable` and `/stm32/motor_2/enable` as
`std_srvs/SetBool`. These are the only supported independent M1/M2 proof
controls; they do not add another serial transport.
They honor `/safety/e_stop` and automatically stop after the configured
`motor_test_max_duration` even if the requesting process disappears.

Velocity uses reliable, volatile, keep-last-1 QoS. Commands are deliberately
not transient-local because a late subscriber must never replay stale nonzero
motion.
