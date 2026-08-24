# Hiwonder ROS Robot Controller V1.2

This is the board-specific hardware reference for the tank robot. It applies
to the Hiwonder ROS Robot Controller with the **STM32F407VET6** MCU, not to
the Rock64's Raspberry-Pi-compatible GPIO header.

## Board identity

- Board: Hiwonder ROS Robot Controller V1.2
- MCU: STM32F407VET6, Cortex-M4, 168 MHz
- Input power: 7–14 V through the blue VIN/GND screw terminal and power switch
- Motor outputs: M1–M4 encoder-motor JST ports; maximum 2 A per channel
- PWM servo outputs: four 5 V PWM channels
- Bus-servo ports: two ports at board-supply voltage
- Interfaces: USB, UART1, Bluetooth/UART2, SBUS, I²C, CAN, USB host, OLED/SPI
- Expansion: bottom GPIO breakout header with power and signal labels

The blue screw terminal used for board power is not the GPIO breakout. The
separate blue 4-position peripheral terminal is labeled `5V`, `GND`, `SDA`,
and `SCL` and is the I²C interface.

## Bottom expansion header: reported signal labels

The following labels are taken from the supplied board reference and photos.
They identify MCU signals, but a signal is only available to an application
when it is not claimed by the active firmware peripheral configuration.

| Group | Signals |
|---|---|
| Power/ground | `3.3V`, `5V`, `GND` |
| CAN | `CANH`, `CANL` |
| Port A GPIO labels | `PA2`, `PA3`, `PA6`, `PA7`, `PA13`, `PA14` |
| Port C GPIO labels | `PC0`, `PC1`, `PC2`, `PC5`, `PC10`, `PC11`, `PC12` |
| Port D/E GPIO labels | `PD4`, `PD10`, `PD15`, `PE2`, `PE3` |

## Current project ownership

These assignments describe the checked-in STM32 firmware and take precedence
over a generic “GPIO available” label:

| Pin | Current use | Expansion status |
|---|---|---|
| `PA13` | SWDIO | Reserved while debugging/programming |
| `PA14` | SWCLK | Reserved while debugging/programming |
| `PC12` | UART5 TX, paired with SBUS receive support | Not a free GPIO in the current image |
| `PA2`, `PA3`, `PA6`, `PA7` | Analog/free GPIO initialization | Candidate GPIOs; verify board routing first |
| `PC0`, `PC1`, `PC2`, `PC5` | Analog/free GPIO initialization | Candidate GPIOs; verify board routing first |
| `PC10` | Free/candidate GPIO | Available only after board-routing verification |
| `PC11` | Free/candidate GPIO | Available only after board-routing verification |
| `PD4`, `PD10`, `PD15` | Analog/free GPIO initialization | Candidate GPIOs; verify board routing first |
| `PE2`, `PE3` | Analog/free GPIO initialization | Candidate GPIOs; verify board routing first |


The expansion labels alone do not prove 5 V tolerance, pull-up availability,
or connector pin order. Treat external signals as 3.3 V logic unless the
board schematic confirms otherwise. Never connect a 5 V signal directly to a
candidate input without confirming the board-level protection or adding a
level shifter/divider.

## Existing production assignments

The current project intentionally keeps these non-expansion connections:

- Host motor link: `PA9`/`PA10`, USART1, through the product UART1 USB-UART
- SG90: `PA11`, J1 only
- Glowy ultrasonic: dedicated four-pin I2C connector (`5V`, `GND`, `SDA`, `SCL`), address `0x77`
- Buzzer: `PA8`
- Battery sense: `PB0`
- IMU: I²C2 `PB10`/`PB11`, interrupt `PB12`

The Glowy module is already supported on the controller's dedicated I2C
connector and shares I2C2 with the onboard IMU. Do not reassign motor encoder,
UART1, SWD, SBUS, IMU, or bus-servo pins just because they appear near the
expansion connector.

## Agent interpretation rule

When a request says “GPIO pin” for this robot, interpret it as a labeled signal
on the Hiwonder controller's bottom expansion header, not a Rock64 Linux GPIO.
First resolve the board label to an STM32 port/pin, then check current firmware
ownership and voltage compatibility before proposing wiring or code.
