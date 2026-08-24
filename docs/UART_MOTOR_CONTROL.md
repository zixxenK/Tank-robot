# Rock64 ↔ STM32 motor link

The current motor image uses the WCH USB-to-UART cable path. ST-Link is a
separate programmer/debugger and is not the application data port.

```text
                         application data
Rock64 USB host ──USB cable──> STM32 board USB-C UART connector
                                  │
                                  └─ WCH bridge 1a86:55d4
                                  └─ USART1 PA9/PA10 (product UART1)
                                     USART3 is factory; USART2 is BLE/auxiliary

                         programming/debug only
Rock64 USB host ──USB cable──> ST-Link 0483:3748
                                  │
                                  └─ SWDIO ─────> STM32 PA13
                                     SWCLK ─────> STM32 PA14
                                     GND   ─────> STM32 GND
                                     NRST  ─────> not connected; use board RST button
```

With both cables connected, `lsusb` should show both identities:

```text
0483:3748  STMicroelectronics ST-LINK/V2       # flash/debug only
1a86:55d4  QinHeng USB Single Serial           # motor protocol only
```

The Rock64 host port is the product-labeled USB-C `UART1`, exposed as
`/dev/rock64_stm32`, at 1000000 8N1. On the STM32 it is USART1 on PA9/PA10.
The wire protocol
is the packed binary frame documented in `communication_protocols.md`:

```text
AA 55 03 LEN 01 COUNT (MOTOR_ID FLOAT32_RPS)* CRC
```

The host sends normalized RPS values from `-1.0` to `1.0`. The STM32 scales
them to its configured `MOTOR_DEFAULT_RPS_LIMIT` and applies the PID loop.
Heartbeat frames are not required and are ignored. A valid motor command must
continue arriving; after 250 ms without one, the STM32 applies an emergency
motor stop.

Before any live movement test, keep motor power disabled and send only the
emergency-stop or zero-speed frame. Hardware motion testing must be performed
with the tracks lifted and the motor-enable switch controlled deliberately.

The deterministic safe-link check is:

```bash
python3 scripts/motor_link_safe_test.py
```

From the Windows checkout, the complete build/flash/readback/launch/proof
workflow always runs on the Rock64:

```powershell
From Windows, use `powershell -File scripts/reflash_rock64.ps1 -Port UART1`.
On the Rock64 itself, use `bash deployment/scripts/rock64_update_and_flash.sh`.
```

There is no alternate production port. The stock 7in1 `USART3/PD8-PD9`
assignment is reference material only and must not be selected for this robot.

It fails if the selected UART produces no valid packed response. Use
`--allow-no-response` only when diagnosing a board that is intentionally not
running the packed custom image.
