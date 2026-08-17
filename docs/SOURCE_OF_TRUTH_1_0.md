# Tank Robot 1.0 Source of Truth

This is the hardware/software state that was physically validated on 2026-08-16.
Treat it as authoritative for all future firmware, Rock64, and agent work.

## Production wiring

| Function | Production assignment |
|---|---|
| Rock64 motor-data connector | Physical USB-C connector labeled `UART1` |
| USB-UART bridge | WCH `1a86:55d4`, exposed as `/dev/rock64_stm32` |
| STM32 peripheral | `USART1` |
| STM32 pins | `PA9` TX, `PA10` RX |
| Serial format | 1,000,000 baud, 8N1 |
| Motor protocol RX | USART1 circular DMA |
| Motor protocol TX | USART1 bounded blocking writes |
| Serial-servo bus | `USART6` |
| Programming/debug | ST-Link `0483:3748` over SWD only |

`USART3` on `PD8/PD9` is the stock Hiwonder 7in1/factory reference endpoint.
It is not the Rock64 host link for this robot and must not be selected for a
production build or deployment.

## Production workflow

Always build, flash, launch, and run the safe UART proof from the Rock64:

```powershell
powershell -File scripts/reflash_rock64.ps1 -Port UART1
```

The workflow must verify the ST-Link readback before testing the motor link.
The stable serial device is `/dev/rock64_stm32`; do not use ST-Link or native
USB CDC as the motor-data port.

For a raised-track bench test, the bounded direct test is:

```bash
python3 scripts/motor_start_stop_test.py \
  --port /dev/rock64_stm32 --rps 0.10 --duration 1.0 --confirm
```

It tests M1, stops, tests M2, and always sends a final emergency stop.

## Validated 1.0 evidence

- Release image built and flashed from the Rock64.
- Validated Release image SHA-256: `1450d9c73c976756b463ca1164339d2b6b8a39c3f5d95d88a87bb4d12b4a56bc`.
- ST-Link readback matched the image byte-for-byte.
- UART proof returned `aa 55 ff 01 01 48`.
- Physical raised-track test moved M1 and M2 at normalized `0.10` speed.
- Final emergency stop was sent successfully.
- `rock64-robot.service` remained intentionally inactive during the bench test.

## Reference boundary

The checked-in 7in1 IOC/source and board photos are evidence/reference only.
They explain the stock `USART3/PD8-PD9` mapping and connector naming; they do
not override this production source of truth. The production firmware and host
configuration must remain on `UART1 -> USART1 -> PA9/PA10`.
