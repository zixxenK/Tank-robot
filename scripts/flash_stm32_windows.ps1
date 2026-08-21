$ErrorActionPreference = "Stop"

Write-Host @"
Direct STM32 flashing from a PC is disabled for this repository.

The production workflow always updates the Rock64 first, then builds, flashes,
verifies, starts the image, and runs the safe UART proof from the Rock64:

  .\scripts\deploy_rock64.ps1

This keeps USB ownership, ST-Link access, udev rules, and /dev/rock64_stm32
validation on the robot host instead of programming from a development PC.
"@

exit 1
