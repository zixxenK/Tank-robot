# STM32 CubeMX Motor Setup Guide

This guide is the canonical bring-up path for the STM32F407 motor controller in this repository.

Use these repository paths together:

- CubeMX project: `firmware/stm32_chassis/stm32_chassis.ioc`
- Firmware sources: `firmware/stm32_chassis/Core/`
- Build entry point: `firmware/stm32_chassis/CMakeLists.txt`

Do not keep editing the root-level `c:/Projects/Tank-Robot/firmware/stm32_chassis/stm32_chassis.ioc` once the repo-local copy exists. The nested repo copy is the one that should travel with code review and commits.

## 1. Goal

Configure the STM32F407VETx to support:

- `USART2` on `PA2`/`PA3` for Rock64 or USB-UART bridge communication
- `TIM3_CH1` on `PA6` for `M1` speed PWM
- `TIM3_CH2` on `PA7` for `M2` speed PWM
- `PA0` as `M1_F` gpio output
- `PA1` as `M1_B` gpio output
- `PA15` as `M2_F` gpio output
- `PB3` as `M2_B` gpio output
- `I2C1` on `PB6`/`PB7` for the MPU6050 path 
- `PA13`/`PA14` as SWD debug pins 

Current firmware meaning:

- `M1` is treated as the left motor
- `M2` is treated as the right motor

If the chassis later proves physically reversed, swap the left/right motor mapping in code rather than re-learning the board pinout.

## 2. Before You Start

1. Open STM32CubeMX.
2. Open `firmware/stm32_chassis/stm32_chassis.ioc` from the nested repo.
3. If CubeMX prompts to migrate the file, allow it, then save it back into the same nested repo path.
4. Confirm the package is STM32Cube FW_F4 `1.28.3` or compatible.

## 3. Configure Debug First

This matters because `PA15` and `PB3` are JTAG-related pins unless JTAG is reduced to SWD.

1. In the left panel, expand `System Core`.
2. Click `SYS`.
3. In the middle configuration panel, set `Debug` to `Serial Wire`.
4. Confirm these stay reserved:
   - `PA13` -> `SYS_JTMS-SWDIO`
   - `PA14` -> `SYS_JTCK-SWCLK`
5. Confirm `PA15` and `PB3` are no longer blocked by full JTAG.

## 4. Configure the Clock Source

1. In the left panel, click `RCC`.
2. Set `High Speed Clock (HSE)` to `Crystal/Ceramic Resonator`.
3. Leave `PH0-OSC_IN` and `PH1-OSC_OUT` enabled.
4. Save.

The checked-in firmware already configures the PLL in code for high-speed runtime, but CubeMX should still know the board has an external HSE source.

## 5. Configure USART2 for Rock64 / Serial Bridge

1. On the chip view, click `PA2`.
2. Select `USART2_TX`.
3. Click `PA3`.
4. Select `USART2_RX`.
5. In the left panel, click `USART2`.
6. Set mode to `Asynchronous` if CubeMX does not do that automatically.
7. Set baud rate to `115200`.
8. Leave word length `8 Bits`, parity `None`, stop bits `1`.

Expected result:

- `PA2` = transmit
- `PA3` = receive

## 6. Configure TIM3 PWM for Motor Speed

1. Click `PA6`.
2. Select `TIM3_CH1`.
3. Click `PA7`.
4. Select `TIM3_CH2`.
5. In the left panel, click `TIM3`.
6. Enable `PWM Generation CH1`.
7. Enable `PWM Generation CH2`.
8. Set prescaler and period so they match firmware expectations:
   - Prescaler: `83`
   - Counter Period: `999`
9. Leave pulse values at `0` initially.

This matches the checked-in firmware PWM assumptions.

## 7. Configure Motor Direction Pins

These are plain digital outputs, not alternate-function pins.

### M1 pins

1. Click `PA0`.
2. Select `GPIO_Output`.
3. Rename it in your notes as `M1_F`.
4. Click `PA1`.
5. Select `GPIO_Output`.
6. Rename it in your notes as `M1_B`.

### M2 pins

1. Click `PA15`.
2. Select `GPIO_Output`.
3. Rename it in your notes as `M2_F`.
4. Click `PB3`.
5. Select `GPIO_Output`.
6. Rename it in your notes as `M2_B`.

Recommended GPIO settings for all four:

- Output type: `Push Pull`
- Pull-up/Pull-down: `No Pull`
- Speed: `Low` or `Medium`

Do not configure these as PWM channels. They are logic-direction lines only.

## 8. Configure I2C1 for MPU6050

1. Click `PB6`.
2. Select `I2C1_SCL`.
3. Click `PB7`.
4. Select `I2C1_SDA`.
5. In the left panel, click `I2C1`.
6. Set mode to `I2C`.
7. Set speed to `100 kHz` for initial bring-up.

## 9. NVIC and DMA

For the current firmware path:

1. Ensure `USART2 global interrupt` is enabled.
2. If you later regenerate DMA configuration for USART2 RX, keep it aligned with the checked-in custom transport implementation.
3. Do not blindly overwrite user sections in transport files after code generation.

## 10. Project Manager Settings

1. Open the `Project Manager` tab.
2. Set project name to `stm32_chassis`.
3. Set toolchain to `CMake`.
4. Keep `Generate Under Root` disabled if the repo layout already matches the checked-in structure.
5. Keep `Keep User Code` enabled.

## 11. Generate Code Safely

1. Click `Generate Code`.
2. If CubeMX warns about overwriting files, stop and review carefully.
3. After generation, compare these files first:
   - `Core/Src/main.c`
   - `Core/Inc/main.h`
   - `Core/Src/stm32f4xx_hal_msp.c`
4. Preserve the custom motor logic, protocol gateway, and transport code already in the repo.

## 12. Canonical Firmware Tree Rule

Use this as the canonical STM32 tree:

- `c:/Projects/Tank-Robot/Tank-robot/firmware/stm32_chassis`

Use this root-level `.ioc` only as a temporary legacy source if needed:

- `c:/Projects/Tank-Robot/firmware/stm32_chassis/stm32_chassis.ioc`

After copying or reconciling the `.ioc`, stop editing the root-level copy. Keep firmware code and CubeMX metadata in the same repo path.

## 13. Motor Self-Test Mode

The firmware now contains a guarded startup self-test.

File:

- `firmware/stm32_chassis/Core/Inc/main.h`

Macros:

- `MOTOR_SELF_TEST_ENABLE`
- `MOTOR_SELF_TEST_DUTY`
- `MOTOR_SELF_TEST_STEP_MS`
- `MOTOR_SELF_TEST_PAUSE_MS`

### To use it

1. Open `firmware/stm32_chassis/Core/Inc/main.h`.
2. Change `MOTOR_SELF_TEST_ENABLE` from `0u` to `1u`.
3. Leave `MOTOR_SELF_TEST_DUTY` low for first power-on. `96` out of `255` is intentionally conservative.
4. Build and flash the STM32.
5. Put the robot on a stand so the tracks are off the ground.
6. Power on and observe this sequence:
   - left motor forward
   - left motor reverse
   - right motor forward
   - right motor reverse
7. After verification, set `MOTOR_SELF_TEST_ENABLE` back to `0u`.

### What to look for

- If `M1_F` causes the wrong direction, swap the forward/reverse interpretation for M1 in code.
- If the left and right sides are swapped, swap the logical left/right mapping in firmware.
- If a motor does not move at all but direction logic toggles, inspect the PWM line for that side.

## 14. Safe Bench Procedure

1. Remove tracks from the ground or lift the chassis.
2. Disconnect any high-level autonomous launch path.
3. Flash only the STM32 first.
4. Run the startup self-test.
5. Confirm direction physically matches labels.
6. Only after that, re-enable normal ROS or binary-bridge control.

## 15. After CubeMX Configuration

Once the `.ioc` is configured, the next engineering steps should be:

1. Regenerate into the nested repo firmware tree.
2. Re-apply any custom merge fixes if CubeMX touched user-managed code.
3. Build the firmware.
4. Flash the firmware.
5. Run startup self-test with tracks lifted.
6. Only then test `/cmd_vel` or vendor motor packets.

## 16. On-Demand Self-Test (No Reflash Required)

The firmware now supports triggering the same motor self-test sequence at runtime.

### Binary/vendor trigger (preferred)

- Function code: `0xF1` (`PROTO_FUNC_SELF_TEST`)
- Payload length: `0`
- Frame format: `AA 55 F1 00 CRC`

The firmware forces a stop before starting the sequence.

### Legacy serial text trigger

- Send: `SELFTEST\n`
- Response: `SELFTEST_OK`

Use this only if you are exercising the legacy text command path.

## 17. micro-ROS-first Motor Bring-up Test Node

You can verify left/right forward/reverse motor behavior through `cmd_vel` without rebuilding firmware.

### Launch via bringup

```bash
ros2 launch robot_bringup rock64_bringup.launch.py use_micro_ros:=true run_motor_bringup_test:=true
```

### What it does

- Publishes a low-speed one-shot sequence to `/cmd_vel`:
   - left forward
   - left reverse
   - right forward
   - right reverse
- Inserts stop phases between each move.
- Automatically exits after completion.

### Safety notes

1. Keep tracks lifted from the bench.
2. Keep test speed conservative for first run.
3. Verify E-stop path before placing robot on ground.
