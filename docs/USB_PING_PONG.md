# Native STM32 USB ping/pong (not the normal board transport)

This diagnostic path uses only the STM32 native USB CDC device. It does not
use the WCH USB-UART adapter on USART1, the robot heartbeat, or motor frames.

The firmware accepts `PING\n` and replies `PONG\n`.

The expected Linux identity is STM32 `0483:5740`. The WCH adapter
`1a86:55d4` exposed as `/dev/ttyACM0` is deliberately rejected.

Install the separate udev alias on the Rock64:

```bash
sudo install -m 0644 deployment/udev/99-rock64-stm32-usb.rules \
  /etc/udev/rules.d/99-rock64-stm32-usb.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

This test applies only to a separately wired/native-CDC hardware variant. The
original Hiwonder controller configures PB14/PB15 as USB host pins, so this
device is not expected on the normal board.

After connecting a compatible native USB OTG device to a Rock64 host USB port,
verify it appears:

```bash
lsusb | grep 0483:5740
ls -l /dev/rock64_stm32_usb
python3 scripts/usb_ping_pong.py
```

Do not point the test at `/dev/rock64_stm32`; that alias identifies the WCH
USART adapter.
