#!/usr/bin/env bash
# fix_input_permissions.sh - Fix input device permissions for PS5 controller
# Run this to allow the ROS bridge to access the PS5 controller

set -eo pipefail

echo "=========================================="
echo "Fix Input Device Permissions"
echo "=========================================="

echo ""
echo "Step 1: Check current permissions"
echo "----------------------------------------------"
ls -la /dev/input/event* | head -5

echo ""
echo "Step 2: Add user to input group"
echo "----------------------------------------------"
INPUT_USER="${INPUT_USER:-${SUDO_USER:-rock64}}"
sudo usermod -a -G input "${INPUT_USER}"
echo "Added ${INPUT_USER} to the input group"

echo ""
echo "Step 3: Create udev rule for input devices"
echo "----------------------------------------------"
sudo tee /etc/udev/rules.d/99-input-permissions.rules > /dev/null <<'EOF'
# Input device permissions for ROS joystick access
SUBSYSTEM=="input", KERNEL=="event[0-9]*", GROUP="input", MODE="0660"
SUBSYSTEM=="input", KERNEL=="js[0-9]*", GROUP="input", MODE="0660"
EOF

echo "✅ Created udev rules for input devices"

echo ""
echo "Step 4: Reload udev rules"
echo "----------------------------------------------"
sudo udevadm control --reload-rules
sudo udevadm trigger

echo ""
echo "Step 5: Fix current device permissions"
echo "----------------------------------------------"
sudo chgrp input /dev/input/event* 2>/dev/null || echo "No event devices to fix"
sudo chmod 660 /dev/input/event* 2>/dev/null || echo "No event devices to fix"
sudo chgrp input /dev/input/js* 2>/dev/null || echo "No joystick devices to fix"
sudo chmod 660 /dev/input/js* 2>/dev/null || echo "No joystick devices to fix"

echo ""
echo "Step 6: Verify permissions"
echo "----------------------------------------------"
ls -la /dev/input/event* | head -5

echo ""
echo "Step 7: Restart service"
echo "----------------------------------------------"
systemctl restart rock64-robot.service

sleep 3
echo ""
echo "Service status:"
systemctl status rock64-robot.service --no-pager | head -15

echo ""
echo "Step 8: Check PS5 bridge logs"
echo "----------------------------------------------"
sleep 2
journalctl -u rock64-robot.service -n 10 --no-pager | grep -i "ps5\|joystick" || echo "No PS5 logs found"

echo ""
echo "=========================================="
echo "Input Permissions Fix Complete"
echo "=========================================="

echo ""
echo "The PS5 controller should now be accessible."
echo "Test with: ros2 topic echo /joy"
