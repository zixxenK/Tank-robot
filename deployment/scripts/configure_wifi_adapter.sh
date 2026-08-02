#!/usr/bin/env bash
# Switch the Ralink MT7601U adapter from virtual-CD to Wi-Fi mode.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[wifi] ERROR: run with sudo" >&2
  exit 1
fi

VIRTUAL_CD_ID="148f:2878"
WIFI_ID="148f:7601"
HELPER="/usr/local/sbin/tank-robot-wifi-modeswitch"
RULE="/etc/udev/rules.d/80-tank-robot-wifi-modeswitch.rules"

if ! modinfo mt7601u >/dev/null 2>&1; then
  echo "[wifi] ERROR: the mt7601u kernel driver is unavailable" >&2
  exit 1
fi
if [[ ! -e /lib/firmware/mt7601u.bin ]]; then
  echo "[wifi] ERROR: mt7601u.bin firmware is unavailable" >&2
  exit 1
fi

install -m 0755 /dev/stdin "${HELPER}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

DEVICE="${1:-}"
[[ -b "${DEVICE}" ]] || exit 0

/usr/bin/python3 - "${DEVICE}" <<'PY'
import fcntl
import os
import sys

device = sys.argv[1]
descriptor = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
try:
    fcntl.ioctl(descriptor, 0x5309)  # CDROMEJECT
finally:
    os.close(descriptor)
PY
EOF

cat > "${RULE}" <<EOF
SUBSYSTEM=="block", KERNEL=="sr[0-9]*", ATTRS{idVendor}=="148f", ATTRS{idProduct}=="2878", RUN+="${HELPER} /dev/%k"
EOF

udevadm control --reload-rules

for root_hub in /sys/bus/usb/devices/usb*/power/control; do
  [[ -w "${root_hub}" ]] && echo on > "${root_hub}"
done

# Avoid probing while the adapter is still changing from virtual-CD mode.
modprobe -r mt7601u 2>/dev/null || true

if lsusb -d "${VIRTUAL_CD_ID}" >/dev/null 2>&1; then
  optical_device="$(
    lsblk --noheadings --raw --paths --output NAME,TYPE \
      | awk '$2 == "rom" {print $1; exit}'
  )"
  if [[ -z "${optical_device}" ]]; then
    echo "[wifi] ERROR: adapter virtual CD block device not found" >&2
    exit 1
  fi
  echo "[wifi] Ejecting ${optical_device} to enter Wi-Fi mode..."
  "${HELPER}" "${optical_device}"
fi

for _attempt in {1..10}; do
  if lsusb -d "${WIFI_ID}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! lsusb -d "${WIFI_ID}" >/dev/null 2>&1; then
  echo "[wifi] ERROR: adapter did not remain enumerated as ${WIFI_ID}" >&2
  echo "[wifi] Move it to a powered USB hub or the USB 3 host port." >&2
  exit 1
fi

wifi_usb_path=""
for candidate in /sys/bus/usb/devices/*; do
  [[ -f "${candidate}/idVendor" ]] || continue
  [[ "$(<"${candidate}/idVendor")" == "148f" ]] || continue
  [[ "$(<"${candidate}/idProduct")" == "7601" ]] || continue
  wifi_usb_path="${candidate}"
  break
done
if [[ -z "${wifi_usb_path}" ]]; then
  echo "[wifi] ERROR: sysfs path for ${WIFI_ID} was not found" >&2
  exit 1
fi
echo on > "${wifi_usb_path}/power/control"
echo -1 > "${wifi_usb_path}/power/autosuspend_delay_ms"

modprobe mt7601u
udevadm settle
sleep 2
nmcli radio wifi on

wifi_interface=""
for candidate in /sys/class/net/*; do
  if [[ -d "${candidate}/wireless" ]]; then
    wifi_interface="${candidate##*/}"
    break
  fi
done

if [[ -z "${wifi_interface}" ]]; then
  echo "[wifi] ERROR: mt7601u probe failed; no WLAN interface appeared" >&2
  echo "[wifi] Check: sudo dmesg | tail -80" >&2
  echo "[wifi] Repeated USB errors -71/-110 indicate port or power instability." >&2
  exit 1
fi

echo "[wifi] Ready: ${wifi_interface} (${WIFI_ID})"
nmcli --terse --fields DEVICE,TYPE,STATE,CONNECTION device status
echo "[wifi] Connect interactively with:"
echo "  sudo nmcli --ask device wifi connect '<SSID>' ifname '${wifi_interface}'"