# STM32 Encoder Telemetry Guide (Host Parser Alignment)

This guide defines a small, deterministic encoder telemetry line format for STM32 so the host parser in `stm32_serial_bridge.py` can ingest wheel encoder ticks reliably.

## Host-side accepted format

`host_ws/src/robot_drivers/robot_drivers/stm32_serial_bridge.py` parses encoder lines that begin with `ENC`:

- `ENC:<left_ticks>,<right_ticks>`
- `ENC,<left_ticks>,<right_ticks>`

Examples:

- `ENC:12345,12310`
- `ENC,-200,220`

The host publishes:

- `/stm32/encoder_ticks` (`std_msgs/Int32MultiArray`) = `[left, right]`
- `/stm32/diagnostics` (`diagnostic_msgs/DiagnosticArray`) with freshness and sample counters

## STM32 patch points

### 1) Control loop context (where counts are already computed)

File: `firmware/stm32_chassis/Core/Src/stm32f4xx_it.c`

Function: `TIM7_IRQHandler()`

This ISR already calls:

- `encoder_update(motors[0], ...)`
- `encoder_update(motors[1], ...)`

Sample patch (rate-limited to avoid UART flooding):

```c
/* USER CODE BEGIN TIM7_IRQn 0 */
extern EncoderMotorObjectTypeDef *motors[4];
static uint8_t enc_print_div = 0;
...
if(__HAL_TIM_GET_FLAG(&htim7, TIM_FLAG_UPDATE) != RESET) {
    __HAL_TIM_CLEAR_FLAG(&htim7, TIM_FLAG_UPDATE);
    encoder_update(motors[0], 0.01f, __HAL_TIM_GET_COUNTER(&htim5));
    encoder_update(motors[1], 0.01f, __HAL_TIM_GET_COUNTER(&htim2));
    ...

    if (++enc_print_div >= 5) { /* 100 Hz / 5 = 20 Hz output */
        enc_print_div = 0;
        /* int32 cast keeps line stable for host parser */
        printf("ENC:%ld,%ld\\r\\n",
               (long)motors[0]->counter,
               (long)motors[1]->counter);
    }
}
/* USER CODE END TIM7_IRQn 0 */
```

Notes:

- Keep output rate around 10–30 Hz.
- If serial bandwidth is constrained, reduce to 10 Hz (`>=10`).
- Keep exactly two integer fields for parser compatibility.

### 2) Alternative patch point in app task (non-ISR)

File: `firmware/stm32_chassis/Hiwonder/System/app.c`

Function: `app_task_entry()` loop

Use when you prefer to avoid `printf` in interrupt context:

```c
static uint32_t last_enc_print_ms = 0;
uint32_t now = HAL_GetTick();
if (now - last_enc_print_ms >= 100) { /* 10 Hz */
    last_enc_print_ms = now;
    printf("ENC:%ld,%ld\\r\\n",
           (long)motors[0]->counter,
           (long)motors[1]->counter);
}
```

## Transport ownership caution

- Ensure encoder lines are emitted on the same UART channel consumed by host bridge mode.
- If using mixed mode, do not share one serial device between micro-ROS and legacy bridge unless explicitly intended.

## Validation checklist

1. Bringup in legacy bridge mode.
2. Confirm host receives lines via serial logs.
3. Confirm ROS topics:
   - `ros2 topic echo /stm32/encoder_ticks`
   - `ros2 topic echo /stm32/diagnostics`
4. Verify diagnostic freshness does not go stale while robot is active.

## Troubleshooting

- No `/stm32/encoder_ticks` updates:
  - Confirm STM32 emits lines starting with `ENC`.
  - Confirm two integers are present.
  - Confirm bridge uses the expected serial device.
- Stale diagnostics:
  - Increase encoder print rate.
  - Check serial framing/noise and UART baud agreement.
