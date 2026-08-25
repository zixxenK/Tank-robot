# Tank Robot documentation index

Start with [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) for the current operating
procedure. It is the milestone-level operator document and defines the active
drive/camera acceptance gate.

Use [ROADMAP.md](ROADMAP.md) for future lab-assistant upgrades and status. The
remaining documents are focused references:

| Area | Reference |
| --- | --- |
| Frozen hardware/software contract | [SOURCE_OF_TRUTH_1_0.md](SOURCE_OF_TRUTH_1_0.md) |
| Rock64 acceptance details | [ROCK64_HARDWARE_ACCEPTANCE.md](ROCK64_HARDWARE_ACCEPTANCE.md) |
| STM32 controller and pins | [HIWONDER_ROS_ROBOT_CONTROLLER_V1_2.md](HIWONDER_ROS_ROBOT_CONTROLLER_V1_2.md), [robot_hardware_reference.md](robot_hardware_reference.md) |
| UART protocol | [communication_protocols.md](communication_protocols.md), [UART_MOTOR_CONTROL.md](UART_MOTOR_CONTROL.md) |
| PC/WSL dashboard and Foxglove | [deployment/pc/README.md](../deployment/pc/README.md) |
| LM Studio | [LM_STUDIO_INTEGRATION.md](LM_STUDIO_INTEGRATION.md) |
| Reliability and known failure modes | [SILENT_FAILURES_AUDIT.md](SILENT_FAILURES_AUDIT.md) |
| End-to-end ROS graph | [e2e_integration.md](e2e_integration.md), [system_topology.md](system_topology.md) |
| ROS communication checks | [ROS2_COMMUNICATION_VERIFICATION.md](ROS2_COMMUNICATION_VERIFICATION.md) |
| Execution and motor protocol references | [TANK_ROBOT_EXECUTION_DIRECTIVE.md](TANK_ROBOT_EXECUTION_DIRECTIVE.md), [UART_MOTOR_CONTROL.md](UART_MOTOR_CONTROL.md) |
| Motors and chassis evidence | [motors/](motors/), [ROCK64_PI2_BUS_PINOUT.md](ROCK64_PI2_BUS_PINOUT.md) |
| Optional LiDAR and HC-SR04 range sensor | [lidar_scanner/](lidar_scanner/), [ULTRASONIC_BUILD_PATH.md](ULTRASONIC_BUILD_PATH.md) |
| Historical board evidence and PDFs | [boardphotos/](boardphotos/), `*.pdf` files in this directory |

The index intentionally keeps historical evidence available while giving
operators one current entry point.
