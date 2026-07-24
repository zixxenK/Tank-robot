# Tomorrow Runbook (2026-07-15)

This is the exact restart plan for getting the robot moving quickly.

## Current status (saved)

- Rock64 kernel and headers are aligned: `6.18.38-current-rockchip64`.
- Realtek A7000 driver is installed via DKMS and loadable as module `8814au`.
- USB path is unstable (hub/device disconnect loop, `error -71`), which causes wlan to disappear.
- ESP32 camera default IP in repo is updated to `192.168.1.125`.
- Biggest blocker for wireless operation is USB stability, not driver build.

## Goal for tomorrow

Get a stable network path first, then verify control path, then camera path.

---

## Phase 1: Fastest way to proceed (recommended)

Use Ethernet on Rock64 and continue bringup now. Do not block on A7000 Wi-Fi.

### 1.1 Verify Rock64 network and ROS basics

```bash
ip link
hostname -I
```

Expected: `end0` is up and has LAN IP.

### 1.2 Verify STM32 serial path and micro-ROS agent

```bash
ls -l /dev/rock64_stm32 || ls -l /dev/ttyACM*
ros2 run micro_ros_agent micro_ros_agent serial --dev /dev/rock64_stm32 -b 115200
```

Expected: agent starts without serial-open failures.

### 1.3 Bring up robot stack (Ethernet mode)

```bash
ros2 launch robot_bringup rock64_bringup.launch.py
```

In another shell:

```bash
ros2 node list
ros2 topic list
```

Expected: bringup nodes present, including teleop bridge and micro-ROS path.

### 1.4 Teleop safety test (robot lifted)

```bash
ros2 topic echo /cmd_vel
```

Expected: controller input changes `/cmd_vel`.

Only test motion with tracks off the ground first.

---

## Phase 2: Recover A7000 Wi-Fi (only after Phase 1 is stable)

### 2.1 Physical setup order

1. Power off Rock64.
2. Unplug ESP32 USB from Rock64.
3. Boot Rock64 with Ethernet only.
4. Plug A7000 directly into Rock64 (no hub) and test.
5. If unstable, use a powered USB hub with its own PSU.

### 2.2 Load module and check interface

```bash
sudo modprobe 8814au
lsmod | grep 8814au
ip link
iw dev
```

Expected: wireless interface appears (`wlan0` or `wlx...`).

### 2.3 If disconnect loop returns, collect proof quickly

```bash
lsusb
sudo dmesg -T | tail -n 120 | grep -Ei "usb|8814|rtl|wlan|disconnect|error -71"
```

Known failure signature from today: repeated hub/A7000 disconnect + `error -71`.

### 2.4 Driver low-power settings (if needed)

Edit:

```bash
sudo nano /etc/modprobe.d/8814au.conf
```

Ensure these lines exist:

```conf
rtw_switch_usb_mode=2
rtw_power_mgnt=0
rtw_enusbss=0
```

Reload:

```bash
sudo modprobe -r 8814au
sudo modprobe 8814au
ip link
iw dev
```

---

## Phase 3: Camera path check (after network is stable)

ESP32 camera expected stream URL:

- `http://192.168.1.125:81/stream`

Test from Rock64:

```bash
curl -I --max-time 5 http://192.168.1.125:81/stream
```

Then verify bridge topic:

```bash
ros2 topic list | grep camera
```

---

## Stop/go criteria

- GO to drive test when:
  - STM32 serial link stable
  - micro-ROS agent running
  - `/cmd_vel` responds
  - no repeated USB disconnect spam
- STOP and keep Ethernet fallback if:
  - A7000 keeps flapping
  - `iw dev` shows no interface after module load

---

## First drive checklist (must-do safety)

1. Robot on stand / tracks off ground.
2. Verify emergency stop path.
3. Short forward/reverse test at low speed.
4. Turn-in-place test low speed.
5. 30-second watchdog/heartbeat observe.
6. Only then floor test.

---

## Quick command block (copy/paste)

```bash
# Baseline checks
uname -r
ip link
iw dev

# Serial + agent
ls -l /dev/rock64_stm32 || ls -l /dev/ttyACM*
ros2 run micro_ros_agent micro_ros_agent serial --dev /dev/rock64_stm32 -b 115200

# Bringup
ros2 launch robot_bringup rock64_bringup.launch.py

# Wi-Fi driver checks
sudo modprobe 8814au
lsmod | grep 8814au
lsusb | grep -Ei "0846:9054|netgear|realtek"
sudo dmesg -T | tail -n 120 | grep -Ei "usb|8814|rtl|wlan|disconnect|error -71"

# Camera check
curl -I --max-time 5 http://192.168.1.125:81/stream
```
