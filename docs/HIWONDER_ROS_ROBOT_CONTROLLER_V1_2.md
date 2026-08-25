# Hiwonder ROS Robot Controller: V1.2 audit record

This document is the human-readable companion to
[`hiwonder_ros_robot_controller_v1_2_profile.json`](hiwonder_ros_robot_controller_v1_2_profile.json).
It distinguishes Hiwonder's published reference material from this robot's
checked-in firmware and physical wiring.

## Important identity finding

The online material is internally inconsistent and does not explicitly publish
a V1.2 hardware revision. The current product page and the hardware-course
schematic call the onboard IMU **MPU6050**. The official program-analysis
chapter 3.5 is titled **QMI8658**, uses the same PB10/PB11/PB12 pins, and the
official downloadable examples are not a revision-specific electrical proof.
Therefore:

- The project may use QMI8658 only as a tested runtime assumption.
- The physical part is accepted only when firmware reads `WHO_AM_I` register
  `0x00` as `0x05` at 7-bit address `0x6A` or `0x6B`.
- A document label, a stale MPU driver, or a product photograph is not enough
  to identify the fitted sensor.

The same separation applies to the UARTs: Hiwonder recommends serial port 2
for a Raspberry Pi/Jetson host and leaves serial port 1 for download, while
this project intentionally uses its product-labeled UART1 WCH bridge on
USART1 PA9/PA10. The factory USART3 PD8/PD9 mapping is reference material,
not the project's transport.

## Official reference inventory

The following is the complete interface inventory extracted from the current
Hiwonder product page and documentation repository:

| Area | Officially documented facts | Confidence/qualification |
|---|---|---|
| MCU | STM32F407VET6, 168 MHz Cortex-M4, 512 KB flash, 192 KB RAM | Product/hardware course |
| Board | 85x60 mm, 39.5 g, 26-pin expansion header, four motor channels, 2 A/channel maximum, protection claims | Current product page; product-family claim, not physical inspection |
| Power | Hardware course: DC 5-12.6 V input; product page: DC 7-14 V input; separate 5 V/5 A SBC output | Sources disagree; verify board marking and battery limits |
| Motor driver | Four encoder-motor channels; schematic names PE9, PE11, PE5, PE6, PE13, PE14, PB8, PB9 | Driver pins listed by schematic; example Motor 1 drive is PE13/PE14 and encoder is PA0/PA1 |
| PWM servo | Four ports: two powered from VIN/battery voltage and two from 5 V | Do not describe all four as 5 V |
| Bus servo | Two ports; schematic names PE7, PG6_TX, PC7_RX | Exact connector-to-signal details belong to board schematic |
| Host serial | Two USB serial ports; serial port 2 recommended for Pi/Jetson; serial port 1 supports download/burning and communication | Program examples use USART3 PD8/PD9 at 1 Mbps 8N1 |
| Bluetooth | UART on PD5/PD6 | Project maps this to USART2 |
| IMU | PB10=SCL, PB11=SDA, PB12=interrupt; hardware text says MPU6050, program chapter says QMI8658 | Unresolved official part identity |
| I2C expansion | External I2C connector on the same bus as the onboard IMU; pull-ups described on the IMU | Do not assume it is a second independent I2C controller |
| LCD | 0.96-inch SPI LCD/ST7735S example; PB13/PC3 plus PD11-PD14 control lines; 80x160, nominal 3.3 V | Hardware intro calls the connector LCD; some text says OLED |
| SBUS | UART5 receive-only on PD2; 100000 baud, 9-bit, even parity, 2 stop bits in the example | Standard inverted SBUS electrical path is on the board |
| USB host | USB host connector; PB15=D- and PB14=D+ | Intended for HID receivers/controllers |
| SWD | PA13=SWDIO and PA14=SWCLK | Programming/debug reservation |
| Buttons | Two user buttons on PE0 and PE1, active low in schematic explanation | Reset is separate NRST button |
| Status LED | User LED on PE10, active-low behavior in schematic explanation | Power indicators are separate board circuitry |
| Buzzer | Hardware schematic text says PA4; program button chapter says PA8 | Unresolved source conflict |
| CAN | CAN connector with a stated 120-ohm termination resistor | MCU signal pins are not named in the text source |
| GPIO | GPIO expansion/SWD header and reserved pins | Availability depends on active peripheral ownership and board routing |
| Protocol | `AA 55`, function, length, data, low-byte CRC over function/length/data | Factory host protocol examples use 1 Mbps over type-C UART2 |

## Checked-in project mapping

The active image is defined by
[`RosRobotControllerM4.ioc`](../firmware/stm32_chassis/RosRobotControllerM4.ioc)
and the production CMake target. Its intentional departures from the factory
reference are:

| Function | Active project mapping |
|---|---|
| Rock64 host | Product-labeled UART1 WCH USB-UART -> USART1 PA9/PA10, 1,000,000 8N1 |
| Factory host reference | USART3 PD8/PD9 remains initialized but is not the production transport |
| IMU | QMI8658 assumption on I2C2 PB10/PB11 at 400 kHz; PB12 is retained as a normal data-ready input because PA12 owns shared EXTI12; both `0x6A` and `0x6B` are probed |
| IMU proof | Host acceptance requires ready diagnostics, a finite sample, valid address, and `WHO_AM_I=0x05` |
| Motors | Physical tank uses two motors; protocol commissions motor IDs 0 and 1. Four board channels remain represented in the firmware API |
| Encoders | M1 PA0/PA1 (TIM5), M2 PA15/PB3 (TIM2), M3 PB6/PB7 (TIM4), M4 PB4/PB5 (TIM3), 1,980 ticks/output revolution for the tank motors |
| Motor PWM | Factory topology is M1 PE13/PE14, M2 PE9/PE11, M3 PE5/PE6, M4 PB8/PB9; the project has only M1/M2 physically commissioned, and its checked-in HAL maps only M4 PB8 while PB9/TIM11 remains non-commissioned |
| PWM servo | Only SG90 J1 PA11 drives a physical output; PA12 and PC8 are assigned to the HC-SR04 path, while PC9 remains unused |
| Bus servo | USART6 PC6/PC7 with PE7/PE8 direction enables |
| Display | SPI2 PB13/PC3 plus PD11/PD12/PD13/PD14 for the LCD |
| Auxiliary UART | USART2 PD5/PD6 |
| SBUS | UART5 RX PD2; PC12 TX is unused for receive-only SBUS |
| Battery | ADC1 channel 8 on PB0 |
| Buzzer/buttons/LED | PA8 / PE1+PE0 / PE10, matching the active IOC and program example rather than the conflicting schematic buzzer sentence |
| USB host/debug | PB14/PB15 and PA13/PA14 |
| Ultrasonic | HC-SR04 direct pulse-timing path: board `5V/GND`, `PC8` trigger, `PA12` echo; no external level shifter |
| Optional I2C sensor | Glowy module at `0x77` on the shared I2C2 bus; retained as a reserved compatibility path |

The active IOC still contains a TIM11 timer object for historical/future use,
but PB9 is configured as analog and `HAL_TIM_MspPostInit()` has no TIM11 pin
route. This is intentional until a fourth motor is physically wired and
commissioned; it must not be described as a working fourth PWM channel.

The active clock is also intentionally recorded from the IOC: PH0/PH1 use an
8 MHz external HSE (`RCC.HSE_VALUE=8000000`) and the firmware derives the
168 MHz system clock from it. Any board note claiming a 25 MHz crystal is
stale and must not be used to regenerate the clock configuration.

The legacy `imu_mpu6050.*`, Fusion, and `imu_porting.c` files are retained as
reference/compatibility material only. They are not in the production CMake
source list and must not be used to infer the physical sensor.

## Source links

- [Hiwonder product page](https://www.hiwonder.com/products/ros-robot-control)
- [Official hardware course](https://wiki.hiwonder.com/projects/ROS-Robot-Control-Board/en/latest/docs/1_Controller_Hardware_Course.html) ([source at audited commit](https://github.com/Hiwonder-docs/ROS-Robot-Control-Board/blob/07746775ee68faa63a97fc4e079e9842481743c9/source/docs/1_Controller_Hardware_Course.md))
- [Official program analysis](https://wiki.hiwonder.com/projects/ROS-Robot-Control-Board/en/latest/docs/3_RosRobot_Controller_Program_Analysis.html) ([source at audited commit](https://github.com/Hiwonder-docs/ROS-Robot-Control-Board/blob/07746775ee68faa63a97fc4e079e9842481743c9/source/docs/3_RosRobot_Controller_Program_Analysis.md#L749))
- [Official documentation source repository](https://github.com/Hiwonder-docs/ROS-Robot-Control-Board/tree/07746775ee68faa63a97fc4e079e9842481743c9)

The online re-verification was performed on 2026-08-24 against repository
commit `07746775ee68faa63a97fc4e079e9842481743c9`. The hardware course still
publishes MPU6050/PB10/PB11/PB12 and PA4 in its schematic text, while the
program-analysis source still has a QMI8658-titled section, PA8 in its button
example, and the factory host example on USART3/PD8-PD9. No online source
examined here establishes that the physical board marked V1.2 contains QMI8658
or publishes the QMI address/WHO_AM_I values; those remain project runtime
acceptance requirements, not official revision facts.

When a future change alters a pin, peripheral, sensor identity, voltage, or
factory/project distinction, update the JSON profile, this document, the IOC,
and the regression contract together.
