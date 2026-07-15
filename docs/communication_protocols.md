# Communication Protocols - Rock64 Ranger

## Overview

This document defines the communication protocols between the three hardware components:

- Rock64 SBC (ROS 2 host)
- STM32F407 (motor controller)
- ESP32-S3 (camera node)

The STM32 reference source-code instructions from Hiwonder are available at:
[Hiwonder STM32 source-code instructions](https://wiki.hiwonder.com/projects/JetAcker/en/jetacker-jetson-nano/docs/1.Getting_Ready.html#stm32-source-code-instruction)

## 1. Rock64 <-> STM32 micro-ROS Transport

### UART Physical Layer

- Interface: USB-UART2 transport used by the micro-ROS agent and STM32 client
- Baud rate: 115200
- Data format: 8N1
- Device: /dev/rock64_stm32 (udev symlink)

### Control Protocol (Rock64 -> STM32)

Format: geometry_msgs/Twist on /cmd_vel.

The STM32 micro-ROS node converts /cmd_vel into left/right track setpoints using differential-drive kinematics and applies a local safety watchdog.

Example:

```text
linear.x = 0.2 m/s
angular.z = 0.0 rad/s
```

This becomes equal left/right track commands on the STM32.

Emergency stop:

```text
command timeout or agent loss
```

The STM32 task stops both motors locally.

### Status Protocol (STM32 -> Rock64)

Telemetry is published as ROS topics rather than ASCII replies.

- /stm32/status for controller state
- /battery/state for future power telemetry
- /imu/data for local sensor payloads when enabled

### Safety Protocol

Watchdog rules:

- Rock64 publishes motion commands through micro-ROS
- STM32 automatically stops motors if no /cmd_vel update is received for 300 ms
- Rock64-side teleop must use a deadman switch or equivalent emergency stop

Implementation:

- STM32: StartDefaultTask() and motor_watchdog() in Core/Src/microros_app.c
- Rock64: ps5_ros_bridge in robot_teleop

## 2. Rock64 <-> ESP32 HTTP Protocol

### HTTP Physical Layer

- Interface: WiFi (station mode)
- Protocol: HTTP
- Port: 81
- Format: MJPEG stream

### Video Stream Protocol

URL: http://<camera_ip>:81/stream

Response format: multipart MJPEG stream.

```text
Content-Type: multipart/x-mixed-replace;boundary=frame

--frame
Content-Type: image/jpeg
Content-Length: <size>

<JPEG binary data>
--frame
Content-Type: image/jpeg
Content-Length: <size>

<JPEG binary data>
...
```

### Camera Configuration

- Resolution: VGA (640x480)
- Format: JPEG
- Quality: 12 (1-31, lower is better)
- Frame rate: about 15-30 FPS depending on WiFi conditions

### ROS 2 Integration

- Node: esp32_camera_bridge in robot_drivers
- Topic: /camera/image_raw (sensor_msgs/Image)
- URL parameter: camera_ip (default: 192.168.1.153)

## 3. ROS 2 Internal Communication

### Topics

| Topic | Message Type | Direction | Description |
| --- | --- | --- | --- |
| /cmd_vel | geometry_msgs/Twist | Input | Linear/angular velocity commands |
| /camera/image_raw | sensor_msgs/Image | Output | Camera feed from ESP32 |
| /joy | sensor_msgs/Joy | Input | PS5 controller input |

### Node Structure

```text
rock64_bringup.launch.py
├── micro_ros_agent (process)
├── ps5_ros_bridge (node)
│   └── Publishes: /cmd_vel
├── stm32 micro-ROS client
│   └── Subscribes: /cmd_vel
│   └── Publishes: status / sensor topics
└── esp32 micro-ROS client (optional / fallback)
    └── Publishes: /camera/image_raw and telemetry topics
```

### QoS Configuration

- Recommended for /cmd_vel: reliability RELIABLE, durability VOLATILE
- Recommended for /camera/image_raw: reliability BEST_EFFORT, durability VOLATILE

## 4. I2C Protocol (STM32 -> MPU6050)

### Physical Layer

- Interface: I2C1 (STM32F407)
- Clock speed: 100 kHz
- Device address: 0x68 (MPU6050)

### Register Map

Gyroscope configuration:

- Register 0x1B: 00001000 (plus/minus 500 deg/s)
- Sensitivity: 65.5 LSB/(deg/s)

Accelerometer configuration:

- Register 0x1C: 00001000 (plus/minus 4 g)
- Sensitivity: 4096 LSB/g

### Data Reading

Read sequence:

1. Write register address 0x3B (ACCEL_XOUT_H)
2. Read 14 bytes from 0x3B
3. Parse accel X/Y/Z (6 bytes), temp (2 bytes), gyro X/Y/Z (6 bytes)

Implementation: MPU6050_ReadData() in mpu6050.c

### STM32F407 Peripheral Pin Map (Hiwonder Cross-Check)

The firmware uses this MCU-level mapping and should be validated against the Hiwonder board wiki before final flashing:

- USART2_TX: PA2 (Rock64 bridge TX from STM32)
- USART2_RX: PA3 (Rock64 bridge RX into STM32)
- TIM3_CH1: PA6 (left motor PWM)
- TIM3_CH2: PA7 (right motor PWM)
- M1_F: PA0 (left motor forward logic)
- M1_B: PA1 (left motor reverse logic)
- M2_F: PA15 (right motor forward logic)
- M2_B: PB3 (right motor reverse logic)
- I2C1_SCL: PB6 (MPU6050 clock)
- I2C1_SDA: PB7 (MPU6050 data)

RM0090-aligned assumptions used by firmware:

- APB1 timer clock is doubled when the APB1 prescaler is not 1
- PWM base: TIM3 at 1 MHz counter clock, ARR=999 (1 kHz PWM)
- UART base: 115200, 8N1 on USART2

## 5. ROS 2 Domain Configuration

### Default Settings

- Domain ID: 42
- RMW implementation: rmw_fastrtps_cpp
- Namespace: rock64_1

### Environment Variables

```bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROBOT_NAMESPACE=rock64_1
```

## 6. Protocol State Machine

### STM32 Motor Controller States

```text
[INIT] -> [IDLE] -> [RUNNING] -> [EMERGENCY_STOP]
              ^        |           |
              |        v           v
              +--------+-----------+
```

State transitions:

- INIT: power-on, initialize peripherals
- IDLE: ready, no motor commands
- RUNNING: executing motor commands
- EMERGENCY_STOP: safety triggered, motors disabled

Triggers:

- INIT -> IDLE: initialization complete
- IDLE -> RUNNING: valid motor command received
- RUNNING -> IDLE: zero-speed command received
- Any -> EMERGENCY_STOP: command timeout, heartbeat loss, or error
- EMERGENCY_STOP -> IDLE: manual reset or heartbeat resume

## 7. Error Handling

### UART Errors

- CRC errors: log and retry
- Timeout: emergency stop motors
- Framing errors: log and reset UART

### HTTP Errors

- Connection lost: retry with exponential backoff
- Invalid MJPEG: log and continue (skip frame)
- Timeout: log warning, continue

### I2C Errors

- NACK: log and retry up to 3 times
- Timeout: log and mark sensor as unavailable
- Data corruption: log and discard reading

## 8. Security Considerations

### Network Security

- ESP32 WiFi uses WPA2-PSK
- Camera stream is unencrypted (local network only)
- Consider VPN for remote access

### Access Control

- Serial port: udev rule limits to rock64 user
- ROS 2: Domain ID isolation prevents cross-network communication

### Fail-Safe Design

- STM32: hardware watchdog independent of firmware
- UART: 200 ms command timeout
- ROS 2: 500 ms heartbeat timeout
- Motors: emergency stop on any communication failure

## 9. Performance Targets

| Metric | Target | Notes |
| --- | --- | --- |
| UART latency | < 10 ms | Command to motor response |
| Camera latency | < 100 ms | Capture to ROS 2 topic |
| Control loop | 50 Hz | /cmd_vel update rate |
| Heartbeat rate | 10 Hz | STM32 -> Rock64 |
| Safety timeout | 200 ms | STM32 motor watchdog |

## 10. Testing Checklist

### UART Protocol

- Rock64 can send motor commands
- STM32 responds with ACK
- STM32 sends heartbeat
- Rock64 detects heartbeat timeout
- Emergency stop works on both ends

### HTTP Protocol

- ESP32 connects to WiFi
- MJPEG stream accessible
- ROS 2 bridge publishes images
- Stream recovers from disconnect

### I2C Protocol

- MPU6050 initializes
- Accelerometer data valid
- Gyroscope data valid
- I2C errors handled gracefully

### Integration

- Full teleop stack works
- All nodes start via systemd
- Auto-recovery from failures
- Logs capture all errors
