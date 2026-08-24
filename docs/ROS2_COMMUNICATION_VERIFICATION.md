# ROS 2 Communication Verification — Tank Robot

This guide adapts the generic ROS 2 communication checklist to this repository.
It is written for a human operator on the Rock64 running ROS 2 Humble.

## What communicates with what

```text
Local Rock64 ROS 2 nodes  <---- DDS/RMW ---->  Optional local PC ROS 2 nodes
        |
        +---- HTTP MJPEG ----> ESP32-S3 camera
        |
        +---- UART1 / USART1 packed binary ----> STM32F407 motor controller
```

Important boundaries:

- DDS does not run inside the STM32 motor firmware.
- DDS does not run inside the ESP32 camera firmware.
- The STM32 link is the validated UART1 -> USART1 -> PA9/PA10 path using
  packed frames and CRC-8/MAXIM.
- The ESP32 camera currently provides an HTTP MJPEG stream. The Rock64 bridge
  republishes it as `/camera/image_raw`.
- A PC or Wi-Fi connection must never be required for the local motor stop
  path.

The hardware and motor transport authority is
[`SOURCE_OF_TRUTH_1_0.md`](SOURCE_OF_TRUTH_1_0.md).

## Current repository baseline

The deployed middleware is Fast DDS:

```bash
echo "$RMW_IMPLEMENTATION"
```

Expected output:

```text
rmw_fastrtps_cpp
```

If the variable is empty, ROS 2 uses its installation default. The example
deployment configuration sets it explicitly in
`deployment/systemd/systemd_config.conf.example`.

The local safety chain is:

```text
/cmd_vel or /agent/cmd_vel_proposed
              |
              v
       safety_gateway
              |
              v
     /ranger/cmd_vel_safe
              |
              v
   stm32_hardened_bridge
              |
              v
       STM32 UART link
```

The existing stop bounds are already layered:

- Teleoperation command timeout: 250 ms.
- Agent command timeout: 100 ms.
- Agent heartbeat timeout: 100 ms.
- STM32 bridge command timeout: 250 ms.
- STM32 firmware command timeout: 250 ms.

Do not add a second generic 500 ms deadman node in front of this chain.
Verify the existing layers instead.

## Human-readable ROS 2 command reference

All commands below are inspection commands unless explicitly marked as a
motion or network-fault test.

### See which nodes are running

```bash
ros2 node list
```

This lists active ROS 2 nodes. For the normal hardware graph, look for
`/safety_gateway` and `/stm32_hardened_bridge`; add
`/esp32_camera_bridge` only when the camera bridge is enabled.

### See which topics exist

```bash
ros2 topic list
```

This shows the topics currently visible in the same ROS domain. A missing
topic usually means its publisher is not running or the nodes are using
different `ROS_DOMAIN_ID` values.

### Check who publishes or subscribes to a topic

```bash
ros2 topic info /ranger/cmd_vel_safe -v
```

The `-v` means verbose. Confirm that the safety gateway publishes this topic
and that only the hardened STM32 bridge subscribes to it. Repeat for
`/camera/image_raw`, `/cmd_vel`, and `/agent/cmd_vel_proposed` when checking
the perception and agent graph.

### Check message type

```bash
ros2 topic type /camera/image_raw
```

Expected output:

```text
sensor_msgs/msg/Image
```

### Check publish frequency

```bash
ros2 topic hz /camera/image_raw
ros2 topic hz /ranger/cmd_vel_safe
ros2 topic hz /stm32/encoder_ticks
```

Each command measures the rate of one topic. Stop it with `Ctrl+C`. A camera
rate lower than expected indicates camera, Wi-Fi, decoding, or Rock64 load
problems. The safety command topic should remain near the configured 50 Hz
control rate even when the input source is idle.

### Check bandwidth

```bash
ros2 topic bw /camera/image_raw
```

This measures the approximate bandwidth consumed by the decoded ROS image
topic. Run it briefly while the camera is active. Do not use this command as
a reason to raise motor limits; it is only a transport measurement.

### Inspect actual QoS

```bash
ros2 topic info /camera/image_raw -v
ros2 topic info /ranger/cmd_vel_safe -v
```

Use the verbose output to compare publisher and subscription QoS. If a topic
has a publisher and subscriber but no messages, check QoS compatibility before
changing code or middleware.

### Echo one message safely

```bash
ros2 topic echo /stm32/diagnostics --once
ros2 topic echo /stm32/encoder_ticks --once
```

`--once` exits after one message. These are read-only commands. Avoid using
`ros2 topic echo` on high-rate image topics because the output is not useful
for measuring image performance.

### Inspect parameters

```bash
ros2 param list /stm32_hardened_bridge
ros2 param get /stm32_hardened_bridge cmd_timeout
ros2 param get /safety_gateway agent_heartbeat_timeout
```

The first command lists parameter names. The second and third print the
configured values so a test record contains the actual safety limits, not
assumed defaults.

### Inspect the complete graph

```bash
rqt_graph
```

Use this when a graphical desktop is available. Verify that no node bypasses
`safety_gateway` to reach the STM32 bridge. On a headless Rock64, use
`ros2 node list` and `ros2 topic info -v` instead.

## Safe baseline procedure

Run the following before changing middleware or QoS:

```bash
ros2 node list
ros2 topic list
ros2 topic info /ranger/cmd_vel_safe -v
ros2 topic info /camera/image_raw -v
ros2 topic hz /ranger/cmd_vel_safe
ros2 topic hz /stm32/encoder_ticks
ros2 topic echo /stm32/diagnostics --once
```

Record the output with the firmware commit, ROS distribution, kernel, active
RMW implementation, and whether the camera is enabled.

For motor testing, use the repository’s guarded scripts and follow the
raised-track requirements in [`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md):

```bash
python3 scripts/motor_start_stop_test.py \
  --port /dev/rock64_stm32 --rps 0.10 --duration 1.0 --confirm
```

This is the only command in the baseline section that intentionally requests
motion. Keep the tracks raised, keep an accessible power cutoff nearby, and
confirm that the script sends its final emergency stop.

## Network fault testing

Network fault tests are not production commands. Perform them with tracks
raised or motor power disabled, and remove the fault after every test.

First identify the interface used for the PC/camera network:

```bash
ip route get 192.168.1.125
```

Look for the `dev` value in the output. Replace `INTERFACE` below with that
value. Never apply `tc` to the UART device; `tc` is for network interfaces
only.

Add 20% packet loss:

```bash
sudo tc qdisc add dev INTERFACE root netem loss 20%
```

Add 100 ms delay instead:

```bash
sudo tc qdisc change dev INTERFACE root netem delay 100ms
```

Remove the injected fault:

```bash
sudo tc qdisc del dev INTERFACE root
```

While the fault is active, repeat the read-only commands for camera rate,
diagnostics, and graph connectivity. Expected behavior:

- Camera-dependent behavior reports stale or unavailable vision data.
- The Rock64 local safety gateway continues running.
- Loss of the optional PC does not bypass or disable the STM32 stop path.
- No old nonzero command is replayed in a burst after the network recovers.

For the strongest stop test, run a short, raised-track motor test and remove
the network connection carrying the command source. Verify the bridge and
STM32 stop within their configured timeouts, then verify that motion does not
resume until a fresh valid command arrives.

## Middleware comparison

Fast DDS is the baseline. If Cyclone DDS is installed, test it without source
changes by setting the environment only for the shell that launches ROS 2:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 node list
```

The first command selects Cyclone DDS for subsequent ROS 2 commands in that
shell. The second confirms that the graph is visible. To return to Fast DDS:

```bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

Record camera bandwidth, image rate, command latency, reconnect behavior, and
CPU/memory use for each middleware. Do not change the production default based
on general reputation; change it only if this robot’s measurements show a
repeatable benefit.

Zenoh is optional future work. The ROS 2 package name and Humble compatibility
must be verified on the Rock64 before it is considered; it does not replace
the STM32 UART protocol.

## QoS policy for this repository

The intended policy is:

| Data | Intended QoS | Reason |
|---|---|---|
| `/camera/image_raw` | Best Effort, volatile, keep-last-1 | Drop old frames rather than queue stale vision data. |
| Detection/obstacle streams | Best Effort, volatile, keep-last-1 | Perception uses the newest available frame. |
| `/ranger/cmd_vel_safe` | Reliable, volatile, keep-last-1 | Local safety gateway to bridge; watchdogs bound stale behavior. |
| Agent and teleop proposals | Explicit volatile, depth 1 | Fresh proposals only; safety gateway validates them. |
| `/tf_static` when introduced | Reliable, transient-local | Late nodes need static transforms. |

The current code uses explicit Reliable QoS for the safe command path but
implicit defaults in several sensor and input nodes. QoS changes must update
both publisher and subscriber sides so they remain compatible.

## MCU, LiDAR, and ultrasonic boundaries

- Keep micro-ROS out of the STM32 path for the current milestone. The firmware
  already has a local command timeout and CRC-protected framing.
- Keep CAN as a future option only if electrical-noise testing shows a real
  UART problem.
- Add the LiDAR and ultrasonic devices as independent ROS 2 sensor adapters
  after their exact models, ports, and protocols are confirmed.
- Use LiDAR/ultrasonic data for obstacle safety. The current monocular image
  obstacle-distance estimate is heuristic and is not an emergency-stop sensor.

## Security baseline

`ROS_DOMAIN_ID=42` separates this robot’s graph from other domains, but it is
not authentication. Before operating on a shared or public network:

1. Restrict ROS 2 traffic to the intended interface/network.
2. Use host firewall rules and SSH key authentication.
3. Keep the physical e-stop and STM32 timeout independent of ROS 2.
4. Add SROS2 permissions only after the graph is stable.

SROS2 permissions must reflect the actual graph: proposal sources publish
proposal topics, `safety_gateway` publishes `/ranger/cmd_vel_safe`, and only
`stm32_hardened_bridge` subscribes to the safe command topic.

## Acceptance checklist

- [ ] Fast DDS baseline recorded.
- [ ] Actual topic publishers, subscribers, and QoS recorded with `-v`.
- [ ] Camera loss produces a perception-health failure, not stale motion.
- [ ] Remote PC loss does not compromise local stop behavior.
- [ ] Bridge and firmware stop after command loss.
- [ ] Reconnection requires a fresh command.
- [ ] CRC and serial reconnect tests remain green.
- [ ] Any alternate RMW implementation is compared with measurements.
- [ ] No test changes the validated UART1 -> USART1 -> PA9/PA10 mapping.
