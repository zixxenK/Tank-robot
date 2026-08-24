# Glowy I2C sensor test

The supported sensor is the Hiwonder Glowy RGB ultrasonic module at I2C
address `0x77`. It uses the controller's labeled `5V`, `GND`, `SDA`, `SCL`
four-pin connector. It does not use trigger/echo wires.

After the Rock64 service is running:

```bash
source /opt/rock64-robot/deployment/scripts/source_host_ws.sh
ros2 topic echo /ultrasonic/range
ros2 topic echo /stm32/diagnostics
```

Place a solid target between 2 cm and 4 m away. A valid reading is finite and
between `0.02` and `4.0` metres. Diagnostics should identify `Hiwonder Glowy`
and show increasing I2C read and valid counters.
