# Rock64 to STM32 Packed Protocol

## Physical Link

- Peripheral: STM32 USART2
- Pins: PD5 TX, PD6 RX
- Host device: `/dev/rock64_stm32`
- Baud: 115200, 8N1
- RX: DMA1 Stream5, circular
- TX: DMA1 Stream6, normal-mode queued DMA

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
| `0x10` | Encoder | `<ii` left/right counts |
| `0x11` | Battery | `<ff` voltage/current |
| `0x12` | IMU | `<ffffff` acceleration/gyro |
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

## Timeouts and Rearming

- A valid motor-speed frame refreshes the command timestamp.
- Heartbeats refresh only the heartbeat timestamp and cannot keep an old motor
  command alive.
- Command timeout or heartbeat timeout invokes immediate PWM/PID shutdown.
- The host bridge sends an emergency stop after every connect/reconnect.
- Motion is armed only after a valid firmware heartbeat and then a fresh safe
  velocity command.

## ROS Topics

| Topic | Type | Producer | Consumer |
| --- | --- | --- | --- |
| `/cmd_vel` | `geometry_msgs/Twist` | Teleop | Safety gateway |
| `/agent/cmd_vel_proposed` | `geometry_msgs/Twist` | Agent | Safety gateway |
| `/agent/heartbeat` | `std_msgs/Bool` | Agent | Safety gateway |
| `/safety/e_stop` | `std_msgs/Bool` | Operator | Safety gateway |
| `/ranger/cmd_vel_safe` | `geometry_msgs/Twist` | Safety gateway | Hardened bridge |
| `/stm32/battery` | `sensor_msgs/BatteryState` | Hardened bridge | Safety gateway |
| `/stm32/encoder_ticks` | `std_msgs/Int32MultiArray` | Hardened bridge | Diagnostics |
| `/stm32/imu` | `sensor_msgs/Imu` | Hardened bridge | Consumers |

Velocity uses reliable, volatile, keep-last-1 QoS. Commands are deliberately
not transient-local because a late subscriber must never replay stale nonzero
motion.
