# Communication Protocols — Rock64 Ranger

## Overview

This document defines all communication protocols between the three hardware components:
- **Rock64 SBC** (ROS2 host)
- **STM32F407** (Motor controller)
- **ESP32-S3** (Camera node)

---

## 1. Rock64 ↔ STM32 UART Protocol

### Physical Layer
- **Interface**: USB-UART (ST-Link V2 or USB-UART adapter)
- **Baud Rate**: 115200
- **Data Format**: 8N1 (8 data bits, no parity, 1 stop bit)
- **Device**: `/dev/rock64_stm32` (udev symlink)

### Command Protocol (Rock64 → STM32)

**Format**: `<motor_id,direction,speed>\n`

- `motor_id`: 0 (left motor) or 1 (right motor)
- `direction`: 0 (reverse) or 1 (forward)
- `speed`: 0-255 (PWM duty cycle)

**Example**:
```
<0,1,200><1,1,200>\n
```
Both motors forward at 78% duty cycle.

**Emergency Stop**:
```
<0,0,0><1,0,0>\n
```

### Response Protocol (STM32 → Rock64)

**Heartbeat**: `HB\n`
- Sent every 100ms from STM32
- Indicates firmware is alive and running

**Command Acknowledgment**: `ACK\n`
- Sent after successfully processing motor command
- Confirms command was received and applied

**Error Messages**: `ERR:<error_code>\n`
- `ERR:TIMEOUT` - Command timeout
- `ERR:I2C` - I2C sensor communication failure
- `ERR:OVERCURRENT` - Motor overcurrent detected

### Safety Protocol

**Heartbeat Monitoring**:
- Rock64 sends `PING\n` every 100ms
- Rock64 expects `HB\n` response within 500ms
- If heartbeat timeout, Rock64 disables motor commands
- STM32 automatically stops motors if no commands received for 200ms

**Implementation**:
- STM32: `motor_safety_check()` in `main.c`
- Rock64: `STM32SerialBridge._send_heartbeat()` and `_serial_read_loop()`

---

## 2. Rock64 ↔ ESP32 HTTP Protocol

### Physical Layer
- **Interface**: WiFi (station mode)
- **Protocol**: HTTP
- **Port**: 81
- **Format**: MJPEG stream

### Video Stream Protocol

**URL**: `http://<camera_ip>:81/stream`

**Response Format**: Multipart MJPEG stream
```
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

**Resolution**: VGA (640x480)
**Format**: JPEG
**Quality**: 12 (1-31, lower is better)
**Frame Rate**: ~15-30 FPS (depends on WiFi conditions)

### ROS2 Integration

**Node**: `esp32_camera_bridge` in `robot_drivers`
**Topic**: `/camera/image_raw` (sensor_msgs/Image)
**URL Parameter**: `camera_ip` (default: 192.168.1.153)

---

## 3. ROS2 Internal Communication

### Topics

| Topic | Message Type | Direction | Description |
|-------|-------------|-----------|-------------|
| `/cmd_vel` | geometry_msgs/Twist | Input | Linear/angular velocity commands |
| `/camera/image_raw` | sensor_msgs/Image | Output | Camera feed from ESP32 |
| `/joy` | sensor_msgs/Joy | Input | PS5 controller input |

### Node Structure

```
rock64_bringup.launch.py
├── stm32_serial_bridge (node)
│   └── Subscribes: /cmd_vel
│   └── Publishes: (none, UART output)
├── esp32_camera_bridge (node)
│   └── Subscribes: (none, HTTP input)
│   └── Publishes: /camera/image_raw
└── (optional) teleop nodes
    └── Subscribes: /joy
    └── Publishes: /cmd_vel
```

### QoS Configuration

**Recommended for /cmd_vel**: `reliability: RELIABLE`, `durability: VOLATILE`
**Recommended for /camera/image_raw**: `reliability: BEST_EFFORT`, `durability: VOLATILE`

---

## 4. I2C Protocol (STM32 → MPU6050)

### Physical Layer
- **Interface**: I2C1 (STM32F407)
- **Clock Speed**: 100kHz
- **Device Address**: 0x68 (MPU6050)

### Register Map

**Gyroscope Configuration**:
- Register 0x1B: `00001000` (±500 deg/s)
- Sensitivity: 65.5 LSB/(deg/s)

**Accelerometer Configuration**:
- Register 0x1C: `00001000` (±4g)
- Sensitivity: 4096 LSB/g

### Data Reading

**Read Sequence**:
1. Write register address 0x3B (ACCEL_XOUT_H)
2. Read 14 bytes from 0x3B
3. Parse: accel X/Y/Z (6 bytes), temp (2 bytes), gyro X/Y/Z (6 bytes)

**Implementation**: `MPU6050_ReadData()` in `mpu6050.c`

---

## 5. ROS2 Domain Configuration

### Default Settings
- **Domain ID**: 42
- **RMW Implementation**: `rmw_fastrtps_cpp`
- **Namespace**: `rock64_1`

### Environment Variables
```bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROBOT_NAMESPACE=rock64_1
```

---

## 6. Protocol State Machine

### STM32 Motor Controller States

```
[INIT] → [IDLE] → [RUNNING] → [EMERGENCY_STOP]
              ↑        ↓           ↓
              └────────┴───────────┘
```

**State Transitions**:
- **INIT**: Power-on, initialize peripherals
- **IDLE**: Ready, no motor commands
- **RUNNING**: Executing motor commands
- **EMERGENCY_STOP**: Safety triggered, motors disabled

**Triggers**:
- INIT → IDLE: Initialization complete
- IDLE → RUNNING: Valid motor command received
- RUNNING → IDLE: Zero-speed command received
- Any → EMERGENCY_STOP: Command timeout, heartbeat loss, or error
- EMERGENCY_STOP → IDLE: Manual reset or heartbeat resume

---

## 7. Error Handling

### UART Errors
- **CRC errors**: Log and retry
- **Timeout**: Emergency stop motors
- **Framing errors**: Log and reset UART

### HTTP Errors
- **Connection lost**: Retry with exponential backoff
- **Invalid MJPEG**: Log and continue (skip frame)
- **Timeout**: Log warning, continue

### I2C Errors
- **NACK**: Log and retry up to 3 times
- **Timeout**: Log and mark sensor as unavailable
- **Data corruption**: Log and discard reading

---

## 8. Security Considerations

### Network Security
- ESP32 WiFi uses WPA2-PSK
- Camera stream is unencrypted (local network only)
- Consider VPN for remote access

### Access Control
- Serial port: udev rule limits to rock64 user
- ROS2: Domain ID isolation prevents cross-network communication

### Fail-Safe Design
- STM32: Hardware watchdog (independent of firmware)
- UART: 200ms command timeout
- ROS2: 500ms heartbeat timeout
- Motors: Emergency stop on any communication failure

---

## 9. Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| UART latency | < 10ms | Command to motor response |
| Camera latency | < 100ms | Capture to ROS2 topic |
| Control loop | 50Hz | /cmd_vel update rate |
| Heartbeat rate | 10Hz | STM32 → Rock64 |
| Safety timeout | 200ms | STM32 motor watchdog |

---

## 10. Testing Checklist

### UART Protocol
- [ ] Rock64 can send motor commands
- [ ] STM32 responds with ACK
- [ ] STM32 sends heartbeat
- [ ] Rock64 detects heartbeat timeout
- [ ] Emergency stop works on both ends

### HTTP Protocol
- [ ] ESP32 connects to WiFi
- [ ] MJPEG stream accessible
- [ ] ROS2 bridge publishes images
- [ ] Stream recovers from disconnect

### I2C Protocol
- [ ] MPU6050 initializes
- [ ] Accelerometer data valid
- [ ] Gyroscope data valid
- [ ] I2C errors handled gracefully

### Integration
- [ ] Full teleop stack works
- [ ] All nodes start via systemd
- [ ] Auto-recovery from failures
- [ ] Logs capture all errors
