# Robot Hardware Reference — Rock64 Tracked Robot

## Canonical transport authority

The validated production wiring is defined by
[`docs/SOURCE_OF_TRUTH_1_0.md`](SOURCE_OF_TRUTH_1_0.md). The Rock64 motor link
is the WCH USB-UART device `1a86:55d4` on the product-labeled UART1 connector,
connected to USART1 on PA9/PA10 at 1,000,000 baud, 8N1. USART2 PD5/PD6 is
BLE/auxiliary; the stock USART3/PD8-PD9 factory mapping is not a production
transport. PB14/PB15 are the factory USB host interface. ST-Link `0483:3748`
is programming/debug only.

Compiled reference for an autonomous tracked robot built on a Hiwonder suspension tank chassis,
with a Rock64 SBC as main compute, an STM32F407VET6 as the real-time motor/sensor controller,
and an ESP32-S3-WROOM-1 as a wireless bridge. Intended to be pasted into an agent's system
prompt / project context so it always has ground-truth specs instead of guessing.

---

## 1. System overview

| Layer | Hardware | Role |
|---|---|---|
| Main compute | Rock64 (Pine64, RK3328) | High-level control, ROS 2 / LangGraph, networking |
| Real-time controller | STM32F407VET6 (custom firmware `rock64_ranger_fw`) | Motor PID, encoders, IMU, servo bus, SBUS in, LCD |
| Wireless bridge | ESP32-S3-WROOM-1 | Bluetooth/Wi-Fi bridge to Rock64 |
| Drivetrain | Hiwonder Suspension Shock-Absorbing Tracked Chassis | 2-motor tracked base |
| Ranging | STL-50B2 TOF LiDAR (UART) | Obstacle/mapping |

The STM32 firmware's pin config (`rock64_ranger_fw.ioc`) closely mirrors Hiwonder's own
**ROS Robot Control Board** reference design for this chassis — same MCU, same 4-channel
encoder/PWM-servo/bus-servo/SBUS/I2C/IMU topology. Section 3 covers that reference board
in full since it's the closest official analog to the custom firmware.

---

## 2. Hiwonder Suspension Shock-Absorbing Tracked Chassis

**Product:** "Track Chassis / Suspension Shock Absorption Full-Metal Tank Robot Encoder Motor / Smart Car Chassis"
**SKU:** 21030201 · **Price:** $79.99 (Standard/Single-layer) · **Source:** hiwonder.com/products/suspended-shock-absorbing-tracked-chassis

### Chassis
- Full aluminum-alloy body, anodized finish, top layer removable for DIY expansion.
- 8-channel high-elasticity carbon-steel tension-spring suspension + micro bearings (per-track shock absorption, not a rigid frame).
- High-quality plastic-particle track with bulged tread for grip on rough terrain.
- Two configurations: **Standard (single layer)** or **Advanced (double layer)** — the double layer adds a second deck for stacking Rock64/sensors/battery separately from the drive electronics.
- Also sold bundled with a LiPo battery + charger.

**Dimensions / weight (single vs double layer):**
| Spec | Value |
|---|---|
| Material | Aluminum alloy, 2mm thickness |
| Width | 194mm (194mm outer bracket; inner rail sub-assembly 143mm) |
| Length | 270mm |
| Weight | Single layer: 1.4kg · Double layer: 1.6kg |
| Package size | 320×240×150mm, 2.3kg shipping weight |
| Color | Black |

### Drive motor — JGB3865-520R45-12
| Spec | Value |
|---|---|
| Motor type | Permanent-magnet brushed, JGB3865-520R45-12 |
| Rated voltage | 12V (voltage range 7–13V) |
| Gear ratio | 45:1 |
| Pre-reduction (motor shaft) speed | 6500 RPM |
| Post-reduction (output) speed | 150 ± 10 RPM |
| Rated torque | 0.15 N·m |
| Stall torque | 0.5 N·m |
| Rated current | 0.1A |
| Stall current | 1.5A (Hiwonder's own control-board spec caps driven motor current at 2A max) |
| Encoder | Hall-effect, quadrature |
| Encoder resolution | **11 PPR** (pulses per revolution, motor shaft — confirmed by Hiwonder support) |
| Output shaft | 6mm-diameter D-shape eccentric shaft |
| Connector | PH2.0, 6-pin |

**Odometry constant:** with 4x quadrature decoding on the STM32 timer, counts per **output shaft**
(track sprocket) revolution = 11 PPR × 4 × 45 (gear ratio) = **1,980 counts/revolution**. Use this
as the base tick-to-distance conversion factor before applying wheel/sprocket circumference.

There are two drive motors total (left track, right track) — this is a 2-motor tank, not 4-motor.

### Battery (if using Hiwonder's stock pack)
| Spec | Value |
|---|---|
| Chemistry/voltage | 11.1V Li-ion, 6000mAh |
| Connector | DC5.5×2.5 (female) or SM-2P (male) |
| Physical size | 86×60×21mm |
| Charger | 12.6V |

### Notes from Hiwonder's own Q&A on this listing
- Motor cable connector is PH2.0/6-pin.
- The bundled "4-Channel Encoder Motor Driver" module is included in the kit (i.e., you don't need
  to separately buy Hiwonder's driver board unless replacing it with a custom design).
- Chassis is only compatible with the original motor/gear ratio — no faster-geared drop-in option sold.
- Not compatible with ArmPi FPV mounting holes; is compatible with LanderPi-style arm add-ons.
- Assembly/wiring tutorials: hiwonder.com.cn/store/learn/126.html

---

## 3. Hiwonder "ROS Robot Control Board" (STM32F407VET6) — reference design

**Product:** hiwonder.com/products/ros-robot-control · **SKU:** 21090069 · **Price:** $49.99

This is Hiwonder's own STM32F407VET6 controller board sold as the electronics partner for chassis
like the one above. It is **not necessarily the exact board in this project** (the project uses a
custom `rock64_ranger_fw` build) — but the pin topology is close enough that this is the best
official reference for cross-checking pin assignments, protocol choices, and default peripheral use.

### Full official spec table
| Parameter | Value |
|---|---|
| MCU | STM32F407VET6, Cortex-M4, 168MHz, hardware FPU, Murata crystal oscillator |
| USB serial ports | 2 |
| Max encoder motors driven | 4 (PID speed control; supports 2WD, 4WD differential, mecanum, omni, steering, Ackermann) |
| Robot arm support | PWM-servo arm or serial-bus-servo arm |
| PWM servo channels | 4, drive voltage 5V |
| Serial bus servo ports | 2, drive voltage = board supply voltage |
| CAN | Integrated CAN chip |
| Expansion port | 26-pin |
| SBUS | 1 port, standard SBUS protocol, for RC receiver input |
| I2C | 1 port; supports 4-channel or 6-channel line-follower modules |
| IMU | Onboard **MPU6050** (6-axis: 3-axis accel + 3-axis gyro) |
| Display | OLED port via SPI |
| Bluetooth | 1 UART-connected module |
| USB HOST | 1 port, for game-controller/receiver dongles |
| Download/debug | One-click serial download; SWD header compatible with J-Link/ST-Link |
| External power out | 1× USB-C, independent 5V/5A rail — can power a Raspberry Pi/Jetson directly |
| Power input | DC 7–14V (12V LiPo confirmed safe to connect directly) |
| Protection | Reverse-polarity, overcurrent, overheat, backflow protection |
| Switches | Separate main power switch and motor-enable switch |
| Buttons/LEDs | Reset button ×1, user buttons ×2, user LED ×1, buzzer ×1 |
| Board size | 85×60mm, 39.5g, 4-layer PCB |
| Mounting hole spacing | 57×49mm |
| Max current per motor channel | 2A |
| Software | ROS1 and ROS2 SDKs (Python 3), full source for motor control / attitude calc / PC comms |

> **Production-image pin ownership (current):** J1/PA11 is the only enabled
> SG90 output. The HC-SR04 uses J4/PC8 for TRIG and J2/PA12 for ECHO. PC9,
> PC10, and PC11 are not HC-SR04 connector signals on this controller.

### Cross-reference to this project's `rock64_ranger_fw.ioc`
| Reference board feature | Project's STM32 pin | Match |
|---|---|---|
| 4× encoder motor ports | TIM2/TIM3/TIM4/TIM5, CH1+CH2 encoder mode | Exact peripheral match; only 2 of 4 channels are wired to the physical chassis motors (left/right track) |
| Reference PWM servo ports | PA11/PA12/PC8/PC9, labeled PWM_SERVO_1..4 | J1/PA11 remains SG90; J4/PC8 is HC-SR04 TRIG and J2/PA12 is HC-SR04 ECHO |
| Serial bus servo port | USART6 (PC6 TX / PC7 RX) + PE7/PE8 as TX/RX bus-direction-enable | Matches Hiwonder's half-duplex bus-servo driver topology exactly |
| SBUS input | UART5 RX (PD2), 100000 baud, 9-bit, even parity, 2 stop bits | Standard SBUS framing, matches |
| Rock64 host link | USART1 (PA9 TX / PA10 RX), 1,000,000 baud | WCH USB-UART motor link on the product connector labeled UART1 |
| Onboard IMU | I2C2 (PB10 SCL / PB11 SDA) + EXTI on PB12 (`IMU_ITR`) | FreeRTOS config has an `mpu6050_data_ready` semaphore — confirms MPU6050, matching the reference board exactly |
| Display | SPI2 TX-only (PC3 MOSI / PB13 SCK) + PD11–14 as LCD_BLK/CS/DC/RES | Reference board uses SPI OLED; project uses a color LCD instead (ST7735-class 4-wire) |
| Auxiliary UART | USART2 (PD5/PD6) | Bluetooth/expansion interface |
| Battery sense | ADC1 IN8 on PB0, labeled BATTERY | Standard voltage-divider ADC monitoring |
| Motor enable input | PD3, `GPIO_Input`, labeled MOTOR_ENABLE | Pin is present, but the current production firmware does not read it or gate PWM; polarity and physical wiring still require board validation |

**Production pin ownership is resolved in the current image:** PA11 is the
single CPU-timed SG90 output, PC8 is the HC-SR04 TRIG output, and PA12 is the
HC-SR04 ECHO EXTI input. The legacy four-servo object array remains only as a
compatibility API; channels 2–4 are no-ops and must not be wired as active
servo outputs.

---

## 4. Rock64 (Pine64) — main compute SBC

**Source:** wiki.pine64.org/wiki/ROCK64 (official Pine64 documentation)

| Spec | Value |
|---|---|
| SoC | Rockchip RK3328, quad-core ARM Cortex-A53 @ up to 1.5GHz, 64-bit |
| GPU | Mali-450 MP2 |
| Video | 4K60P HDR decode, VP9 / 10-bit H.265 / H.264 |
| RAM | 1GB / 2GB / 4GB LPDDR3 (1600–1866MHz depending on revision), board-dependent |
| Storage | eMMC module socket + microSD slot (SPI flash removed on current-production boards) |
| USB | USB 3.0 (+ other USB ports depending on revision) |
| Expansion | Pi-2 bus, Pi-P5+ bus (I2C/SPI/UART/GPIO headers, Raspberry-Pi-compatible pinout family) |
| Board dimensions | 85 × 56 × 18.8mm (credit-card size) |
| Power input | 5V DC @ 3A via 3.5mm OD / 1.35mm ID "Type H" barrel connector (2A acceptable if USB 3.0 isn't heavily loaded) |
| OS support | Debian, Android 7/7.1, Yocto, Manjaro, DietPi, LibreELEC, and other community Linux builds |
| Supply commitment | 4GB variant designated Long-Term-Supply, Pine64 committed through ~2022+ |

Given the project's `mpu6050_data_ready`/FreeRTOS naming and "master" UART link at 1Mbaud, the Rock64
is talking to the STM32 over the custom USART1 PA9/PA10 pair (not native USB), which is a
deliberate design choice worth keeping documented — it bypasses the reference board's USB-CDC approach.

---

## 5. ESP32-S3-WROOM-1 — wireless bridge module

**Source:** espressif.com/en/module/esp32-s3-wroom-1-en + official Espressif datasheet

| Spec | Value |
|---|---|
| SoC | ESP32-S3 (Xtensa dual-core LX7, up to 240MHz) |
| Wireless | Wi-Fi 4 (802.11 b/g/n, 2.4GHz) + Bluetooth LE 5.0 |
| Antenna | On-board PCB antenna (module is "-WROOM-1"; the "-WROOM-1U" variant swaps this for a U.FL connector) |
| Flash options | 4 / 8 / 16 MB (variant-dependent, e.g. N4, N8, N16 suffixes) |
| PSRAM options | 0 / 2 / 8 MB (variant-dependent, e.g. R2, R8 suffixes) |
| Module dimensions | 18 × 25.5 × 3.1mm |
| GPIO | Up to 45 physical pins on the chip; the WROOM-1 module breaks out the majority as usable GPIO (pin count usable depends on flash/PSRAM interface pins reserved for octal PSRAM variants) |
| Peripherals | USB OTG (full-speed, native USB device/host), SPI, I2S, I2C, UART, LEDC (PWM), full-speed CAN/TWAI (ISO 11898-1), 12-bit ADC, capacitive touch sensing, temperature sensor |
| AI acceleration | Vector instructions for NN inference / signal processing (AI-oriented variant of the ESP32 line) |
| Power | 3.3V supply, ≥500mA recommended (RF TX bursts exceed average draw) |
| Frameworks | ESP-IDF (official SDK, `idf.py set-target esp32s3`), Arduino-ESP32 core, MicroPython, Matter |
| Temperature range | -40 to 85°C (most variants); -40 to 65°C for R8 (octal PSRAM) variants; -40 to 105°C for "-H4" high-temp variants |

**Design notes relevant to bring-up:**
- EN (reset) pin is only weakly pulled up internally (~2MΩ) — add an external 100kΩ pull-up and
  consider a reset-supervisor IC (e.g. MAX809) rather than a bare RC network if the 3.3V rail has
  significant bulk capacitance.
- Native USB-OTG means it can be flashed directly over USB and enumerate as a USB device or host —
  relevant to the earlier `esptool`/USB-JTAG debug-unit flashing workflow (`303a:1001 Espressif USB
  JTAG/serial debug unit` is exactly this native USB-Serial/JTAG peripheral, not a separate USB-UART chip).
- SPI routed through the GPIO matrix caps out around 80MHz; IO_MUX-direct pins are needed to go faster.

---

## 6. Open questions to track

- Which exact chassis SKU (single vs double layer, with/without bundled battery) is physically on hand. **DOUBLE IS ON HAND**
- Whether the four PWM_SERVO GPIO pins are meant to become hardware-timer PWM (TIM1/TIM9) or stay bit-banged. **DOCUMENTED IN SECTION 5 - RECOMMENDATION PROVIDED**
- Confirm the ESP32-S3 module variant in use (flash/PSRAM size — N4/N8/N16, R2/R8) since it isn't
  identifiable from `lsusb`/`dmesg` output alone; check the module's printed part marking or query it
  via `esptool.py flash_id`.
- Whether the Rock64↔STM32 link over USART1 at 1Mbaud is a custom packet protocol or reuses any of
  Hiwonder's open-source ROS SDK framing. **The validated production transport is UART1/USART1.**

---

## 5. STM32F407VET6 Pin Mapping — rock64_ranger_fw Configuration

Complete pin-by-pin mapping of the custom firmware configuration, cross-referenced with the Hiwonder reference board and component assignments.

### Power & Clock
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PH0-OSC_IN | RCC_OSC_IN | External 25MHz crystal | System clock source (HSE) |
| PH1-OSC_OUT | RCC_OSC_OUT | External 25MHz crystal | System clock source (HSE) |

### JTAG/SWD Debug
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PA13 | SYS_JTMS-SWDIO | SWD debug interface | Standard STM32 SWD data line |
| PA14 | SYS_JTCK-SWCLK | SWD debug interface | Standard STM32 SWD clock line |

### USB
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PB14 | USB_OTG_HS_DM | USB host | Factory USB host data minus |
| PB15 | USB_OTG_HS_DP | USB host | Factory USB host data plus |

### Analog/ADC
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PB0 | ADCx_IN8 (BATTERY) | Battery voltage divider | Monitors battery voltage for safety system |

### I2C
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PB10 | I2C2_SCL | MPU6050 IMU | I2C clock for IMU sensor |
| PB11 | I2C2_SDA | MPU6050 IMU | I2C data for IMU sensor |

### SPI (LCD Display)
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PB13 | SPI2_SCK | LCD clock | SPI clock for ST7735-class LCD |
| PC3 | SPI2_MOSI | LCD data | SPI MOSI for LCD (TX-only simplex) |

### UART/USART Communications

#### Rock64 Host Link
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PA9 | USART1_TX | UART1 USB-C host link | Binary protocol TX to Rock64 |
| PA10 | USART1_RX | UART1 USB-C host link | Binary protocol RX from Rock64 |

#### Auxiliary UART
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PD5 | USART2_TX (`BLE_TX` label) | Auxiliary/Bluetooth port | Not the Rock64 motor transport |
| PD6 | USART2_RX (`BLE_RX` label) | Auxiliary/Bluetooth port | Not the Rock64 motor transport |

#### SBUS RC Input
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PD2 | UART5_RX (SBUS_RX) | RC receiver | SBUS protocol input (100000 baud, 9E2) |
| PC12 | UART5_TX | SBUS (unused) | TX not needed for SBUS receive-only |

#### Serial Bus Servo
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PC6 | USART6_TX (SERIAL_SERVO_TX) | Serial bus servo | Half-duplex servo bus transmit |
| PC7 | USART6_RX (SERIAL_SERVO_RX) | Serial bus servo | Half-duplex servo bus receive |
| PE7 | GPIO_Output (SERIAL_SERVO_TX_EN) | Bus direction control | TX enable for half-duplex bus |
| PE8 | GPIO_Output (SERIAL_SERVO_RX_EN) | Bus direction control | RX enable for half-duplex bus |

### Timer/Encoder Inputs (Motor Encoders)
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PA0 | TIM5_CH1 | Motor encoder 4 | Quadrature encoder input channel 1 |
| PA1 | TIM5_CH2 | Motor encoder 4 | Quadrature encoder input channel 2 |
| PA15 | TIM2_CH1_ETR | Motor encoder 2 | Quadrature encoder input channel 1 |
| PB3 | TIM2_CH2 | Motor encoder 2 | Quadrature encoder input channel 2 |
| PB4 | TIM3_CH1 | Motor encoder 3 | Quadrature encoder input channel 1 |
| PB5 | TIM3_CH2 | Motor encoder 3 | Quadrature encoder input channel 2 |
| PB6 | TIM4_CH1 | Motor encoder 1 | Quadrature encoder input channel 1 |
| PB7 | TIM4_CH2 | Motor encoder 1 | Quadrature encoder input channel 2 |

**Note:** Only encoders 1 (TIM4) and 2 (TIM2) are actively used for the 2-motor tracked chassis (left/right track). Encoders 3 (TIM3) and 4 (TIM5) are configured but not physically connected to the chassis motors.

### Timer PWM Outputs (Motor Control)
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PE9 | TIM1_CH1 | Motor PWM channel 1 | Hardware PWM for motor driver M1 |
| PE11 | TIM1_CH2 | Motor PWM channel 2 | Hardware PWM for motor driver M2 |
| PE13 | TIM1_CH3 | Motor PWM channel 3 | Hardware PWM for motor driver M3 (unused) |
| PE14 | TIM1_CH4 | Motor PWM channel 4 | Hardware PWM for motor driver M4 (unused) |
| PE5 | TIM9_CH1 | Additional PWM | Reserved for future use |
| PE6 | TIM9_CH2 | Additional PWM | Reserved for future use |
| PB8 | TIM10_CH1 | Additional PWM | Reserved for future use |
| PB9 | TIM11_CH1 | Additional PWM | Reserved for future use |

### GPIO Outputs (LCD Control)
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PD11 | GPIO_Output (LCD_BLK) | LCD backlight | LCD backlight control |
| PD12 | GPIO_Output (LCD_CS) | LCD chip select | LCD chip select (ST7735) |
| PD13 | GPIO_Output (LCD_DC) | LCD data/command | LCD data/command select |
| PD14 | GPIO_Output (LCD_RES) | LCD reset | LCD hardware reset |

### GPIO / HC-SR04 / SG90 ownership (production image)
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PA11 | `PWM_SERVO_1` GPIO output | SG90 J1 | Sole production PWM servo output |
| PA12 | `HC_SR04_ECHO` rising/falling EXTI input | J2 signal | Never drive as a servo output |
| PC8 | `HC_SR04_TRIG` GPIO output | J4 signal | 10 us trigger pulse |
| PC9/PC10/PC11 | Unused by HC-SR04 | None | Do not use as the sensor pair |

The legacy reference-board timer-remapping suggestions are historical and do
do not apply to the production image. Changing PC8 or PA12 back to servo
outputs would break ultrasonic capture and is not an approved firmware change.

#### Issue 2: WCH motor transport documentation
**Resolution:** The approved custom image uses the physical UART1 connector
and USART1 (PA9/PA10) for the Rock64 connection, as defined by the canonical
source-of-truth document.

**Impact:**
- Documentation confusion when referencing pin functions
- Potential confusion if Bluetooth module is added later

**Recommendation:**
- Update pin labels in CubeMX from BLE_TX/BLE_RX to ROCK64_TX/ROCK64_RX
- Update documentation to reflect actual usage
- USART2 (PD5/PD6) remains the auxiliary/Bluetooth module; USART6 (PC6/PC7)
  owns serial-servo traffic.

---

### GPIO Outputs (Miscellaneous)
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PA8 | GPIO_Output (BUZZER) | Buzzer | Audio feedback buzzer |
| PE10 | GPIO_Output (LED_SYS) | System LED | Status indicator LED |

### GPIO Inputs
| Pin | Signal | Component | Rationale |
|---|---|---|---|
| PD3 | GPIO_Input (MOTOR_ENABLE) | Unconsumed motor-enable input | Current firmware does not read this pin or use it as a PWM safety interlock; do not treat it as the emergency cutoff |
| PE0 | GPIO_Input (KEY2) | User button 2 | General-purpose user input |
| PE1 | GPIO_Input (KEY1) | User button 1 | General-purpose user input |
| PB12 | GPXTI12 (IMU_ITR) | MPU6050 interrupt | IMU data ready interrupt for FreeRTOS semaphore |

---
