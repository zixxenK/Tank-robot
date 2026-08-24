# HC-SR04 reference

The original sensor reference is preserved as [`HC-SR04.PDF`](HC-SR04.PDF).
This Markdown file intentionally contains only the project decision and points
to the authoritative implementation path:

[`HC-SR04 production build path`](../ULTRASONIC_BUILD_PATH.md)

## Project decision

For the Hiwonder ROS Robot Controller V1.2 in this repository:

- `J4` signal (`S`) / STM32 `PC8` is `TRIG`.
- `J2` signal (`S`) / STM32 `PA12` is `ECHO`.
- `J4` `+5V` powers the sensor and `J4` `GND` is the common ground.
- The 5 V `ECHO` line must be level-protected until the complete board input
  path is verified.
- The sensor is measured by the STM32 and reported over the existing UART link;
  it is not a Rock64 GPIO or Arduino peripheral.

`PC10/PC11` are not an alternate production path. `J1/PA11` remains reserved
for the SG90. Do not use an older firmware image that configures `J2/PA12` or
`J4/PC8` as servo outputs.
