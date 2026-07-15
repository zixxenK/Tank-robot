# Rock64 Ranger — Tank Robot

A differential-drive tracked robot built on the **Hiwonder tank chassis**,
integrating STM32, ESP32-S3, and Rock64 in a clean layered architecture.

## Hardware

| Component | Role |
| --- | --- |
| **STM32F407** | Real-time motor control and encoder/PID loop via micro-ROS |
| **ESP32-S3** | Camera, telemetry, and expansion-hub fallback via Wi-Fi |
| **Rock64 SBC** | ROS 2 runtime, teleoperation, and micro-ROS agent host |
| **Hiwonder Tank Chassis** | Differential-drive tracked platform |

## Repository Structure

```text
├── .devcontainer/       # ROS2 Jazzy + ARM toolchain dev environment (Ubuntu 24.04)
├── firmware/
│   ├── stm32_chassis/   # STM32F407 firmware (CMake, ARM GCC)
│   └── esp32_sensors/   # ESP32-S3 camera firmware (PlatformIO)
├── ros2_ws/src/
│   ├── robot_bringup/   # Launch files & hardware configuration
│   ├── robot_teleop/    # PS5 controller + keyboard teleop nodes
│   └── robot_drivers/   # STM32 serial bridge + ESP32 camera bridge
├── deployment/          # systemd auto-start infrastructure
├── scripts/             # Flashing and utility scripts
└── docs/
    ├── system_topology.md           # Full architecture & Endgame structure
    ├── communication_protocols.md   # All communication protocols
    └── flashing_guide.md            # Complete flashing instructions
```

## Quick Start (DevContainer)

1. Open in VS Code → **Reopen in Container**
2. The container installs ROS2 Jazzy, ARM GCC, and PlatformIO automatically.

## Building

```bash
# STM32 firmware
cd firmware/stm32_chassis
./scripts/sync_stm32_drivers.sh
cmake -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake
cmake --build build

# ESP32 firmware
cd firmware/esp32_sensors
pio run -e esp32cam

# ROS2 workspace
cd ros2_ws
colcon build --symlink-install
```

Note: STM32 firmware is intentionally built only from local `firmware/stm32_chassis/Drivers/` content sourced from official ST repositories.

## Flashing

See [docs/flashing_guide.md](docs/flashing_guide.md) for complete flashing instructions.

```bash
# Flash STM32
./scripts/flash_stm32.sh --build

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\flash_stm32_windows.ps1 -Build -Verify

# Flash ESP32
cd firmware/esp32_sensors
pio run -e esp32cam -t upload
```

## Deployment on Rock64

```bash
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto
```

## Communication Protocols

The baseline system is micro-ROS-first:

1. **Rock64 ↔ STM32**: micro-ROS over USB/UART2 for motor control, encoders, and status telemetry.
2. **Rock64 ↔ ESP32**: micro-ROS over Wi-Fi for camera/telemetry expansion hubs or fallback peripherals.
3. **STM32 ↔ local peripherals**: I2C/SPI/PWM as needed for the chassis controller.

See [docs/communication_protocols.md](docs/communication_protocols.md) for the lower-level transport notes and firmware constraints.

## ROS 2 Node Topology (Micro-ROS First)

The recommended Jazzy topology is:

1. Rock64 runs:
    - `micro_ros_agent` (transport gateway)
    - `ps5_ros_bridge` (DualSense to `/cmd_vel`)
2. STM32 runs micro-ROS client:
    - Subscribes to `/cmd_vel`
    - Publishes wheel/encoder and status telemetry
3. ESP32 expansion hubs run micro-ROS clients:
    - Publish IMU/power/sensor data
    - Subscribe to auxiliary outputs (LEDs, effects, etc.)

If you later want Rock64-side per-track outputs for a specific expansion hub, keep the optional `cmd_vel_to_tracks` node as a utility, but do not put it in the default motion path.

Launch all Rock64-side nodes:

```bash
cd ros2_ws
source install/setup.bash
ros2 launch robot_bringup rock64_bringup.launch.py
```

Migration mode (if STM32/ESP32 are still on legacy bridges):

```bash
ros2 launch robot_bringup rock64_bringup.launch.py use_legacy_bridges:=true
```

## Documentation

- [System Topology](docs/system_topology.md) - Architecture and directory structure
- [Communication Protocols](docs/communication_protocols.md) - All protocol specifications
- [Flashing Guide](docs/flashing_guide.md) - Complete flashing instructions
- [Deployment Guide](deployment/docs/deployment_guide.md) - Rock64 deployment setup

## Supported Platforms

- **Development**: Ubuntu 24.04 (Jazzy) or Ubuntu 22.04 (Humble)
- **Deployment**: Rock64 SBC (Ubuntu 24.04 recommended)
- **STM32**: STM32F407VGTx
- **ESP32**: ESP32-S3-DevKitC-1

## Safety Features

- Motor safety watchdog (200ms command timeout)
- Heartbeat monitoring (500ms timeout)
- Emergency stop on communication failure
- Hardware watchdog on STM32

## License


## cubemx stm32 setup
Part 1: Setting up the Chip's "Brain" in STM32CubeMX
Step 1: Find your chip
Double-click and open STM32CubeMX on your computer.

Click the big button that says Access to MCU Selector (it looks like a picture of a little black microchip).

In the top-left corner, look for a search box that says Part Number. Type in: STM32F407VE

Look at the list on the right. You will see STM32F407VETx. Double-click it!

Boom! A giant picture of your exact chip with all its little legs (pins) will appear on your screen.

Step 2: Turn on the chip's ears (Enable Debugging)
If we don't do this step, the chip won't listen to our computer when we try to send it code!

On the far-left menu, click on System Core to open it up.

Inside that list, click on SYS.

In the middle of your screen, look for Debug and change it from "Disable" to Serial Wire.
(You will see two pins on your chip picture turn green. This is correct!)

Step 3: Tell the chip how fast to think (Enable the Heartbeat Clock)
Your board has a tiny metal oscillator (crystal) that acts as the chip's heartbeat. We need to tell the chip to use it.

In that same left-side menu under System Core, click on RCC.

Look at the top option: High Speed Clock (HSE).

Change it from "Disable" to Crystal/Ceramic Resonator.

Step 4: Make a simple light switch (Enable an LED pin)
Because this is a custom robot board, we don't know exactly which pin your board's manufacturer wired to the built-in LED, but let's configure a generic pin (we will use PA5 as an example) so you see how it is done.

Look at the giant picture of the chip on the right.

Find the pin labeled PA5 (you can use the search box at the bottom right of the chip window to find it—it will flash red).

Left-click directly on PA5.

A tiny list will pop up. Click on GPIO_Output.
(The pin will turn green. This tells the chip: "This pin is now a light switch I can turn ON or OFF in my code!")

Part 2: Exporting to VS Code
Step 5: Tell the project to save for VS Code
Now we must configure the project settings so it generates files that VS Code can easily read.

Look at the very top of your screen and click the tab called Project Manager.

Project Name: Type in a name (like MyFirstRobotProject).

Project Location: Click Browse and choose a folder on your computer where you want to save your code.

Toolchain / IDE: This is the most important step! Click the dropdown and change it to CMake. (Modern VS Code uses CMake to build STM32 projects automatically).

Step 6: Generate the code!
Look at the very top-right corner of the window.

Click the big green button that says Generate Code.

A progress bar will pop up. Once it finishes, a window will appear saying "Successfully generated". Click Close (don't open the folder just yet).

Part 3: Opening and Coding in VS Code
Now, let's open up VS Code (which we configured with your network settings earlier) and pull in our newly generated code!

Step 7: Install the STM32 Extension in VS Code
Open VS Code.

Click on the Extensions icon on the left sidebar (it looks like four blocks/squares).

Search for: STM32 VS Code Extension (or STM32CubeIDE for Visual Studio Code).

Click Install. (This will automatically install everything VS Code needs to read your chip's files!)

Step 8: Open your project
In the top-left menu of VS Code, click File -> Open Folder...

Find the folder you created in Step 5 (the one with your project name) and click Select Folder.

Look at the bottom-right corner of your screen. A little pop-up will appear saying:

"Would you like to configure the discovered CMake Project as a STM32Cube Project?"

Click Yes!
Recommended WorkflowOpen or Create your .ioc file in CubeMX: Verify that your pinout, clock tree, and middleware (like FreeRTOS) are configured exactly as you need them for your hardware.  Generate Code: Tell CubeMX to generate the project files (typically for a "Makefile" or "CMake" project structure, which VS Code prefers).Open in VS Code: Once the files are generated, open the project folder in VS Code. The extension will then use that CMakeLists.txt file (or Makefile) to handle the building and debugging process.
1. Identify Pin and Peripheral AvailabilityCheck Pinout Status: Open your stm32_chassis.ioc file in CubeMX to see which pins are still labeled as "GPIO" or are completely unused.  Peripheral Mapping: Consult the STM32F407 reference manual to determine which pins support the specific communication protocol you need (e.g., I2C, SPI, UART, or additional ADC channels).  Resource Conflict Avoidance: Ensure that the new peripheral you intend to add does not conflict with existing assignments, such as those already defined for your motors or USB interface.  2. Configure via STM32CubeMXUpdate Configuration: In the CubeMX GUI, enable the new peripheral (e.g., a second I2C bus or an additional timer).  Generate Code: Click "Generate Code" to allow CubeMX to update the HAL initialization files. Because you have ProjectManager.KeepUserCode=true enabled, your existing custom code will remain safe within the /* USER CODE BEGIN ... */ blocks.  3. Update Firmware and Build SystemIntegration: Add the necessary initialization code for the new peripherals in main.c or within the generated MX_<Peripheral>_Init() functions.  CMake Adjustment: If you add new source files for the new hardware, you must add them to the target_sources section in your CMakeLists.txt file to ensure they are compiled correctly.  Linker Script (if needed): If your new additions require significant memory or unique memory sections, you may need to update the STM32F407xx_FLASH.ld file.  4. TestingBench Test: After adding new hardware, verify the functionality using the same bring-up methodology used for your motors, ensuring that the new peripheral does not interfere with the stability of the existing system.  