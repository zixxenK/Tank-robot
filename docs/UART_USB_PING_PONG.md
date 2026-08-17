# USB-cable UART ping/pong diagnostic

This is a historical diagnostic image. The current motor-control image uses
packed binary motor frames and intentionally ignores ASCII `PING`/`PONG`.

This diagnostic is for a historical test image only. The production board
connector enumerates on the Rock64 as the WCH USB Single Serial device
(`1a86:55d4`), carrying the motor link on USART3 PD8/PD9 at 1000000 8N1.
The current firmware does not implement ASCII PING/PONG. The historical
diagnostic image polls USART3 and replies `PONG\n` only after receiving
`PING\n` on the corresponding UART.

It initializes no native USB CDC, FreeRTOS, DMA transfers, motors, heartbeat,
ROS protocol, or unsolicited output. ST-Link remains a separate SWD
programmer and is not used as the data port.

Build artifact:

```text
firmware/stm32_chassis/build/Release/RosRobotControllerM4.bin
SHA-256: A24C2F8957CEB968AC6AE221F318C4AFFDF0C5A92CFBC49556BA985026A299C8
```

On the Rock64, stop any service that may open the serial device, flash with
the separate ST-Link, then run:

```bash
python3 scripts/uart2_ping_pong.py --port /dev/rock64_stm32 --baud 1000000
```

Expected USB identities while both cables are connected:

```text
0483:3748  ST-LINK/V2              # programmer only
1a86:55d4  QinHeng USB Single Serial # ping/pong data path
```

The native CDC identity `0483:5740` is not expected for this image.
