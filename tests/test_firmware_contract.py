"""Static contracts for firmware safety integrations that need hardware proof."""

from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _board_profile() -> dict:
    return json.loads(
        _read("docs/hiwonder_ros_robot_controller_v1_2_profile.json")
    )


def test_iwdg_is_enabled_built_and_serviced_by_protocol_task():
    hal_conf = _read("firmware/stm32_chassis/Core/Inc/stm32f4xx_hal_conf.h")
    cmake = _read("firmware/stm32_chassis/cmake/stm32cubemx/CMakeLists.txt")
    watchdog = _read("firmware/stm32_chassis/Hiwonder/System/watchdog.c")
    protocol = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    assert "HAL_IWDG_MODULE_ENABLED is intentionally not enabled" in hal_conf
    assert "stm32f4xx_hal_iwdg.c" not in cmake
    assert "IWDG->KR = 0xCCCCU" in watchdog
    assert "IWDG->KR = 0xAAAAU" in watchdog
    assert "Watchdog_Refresh();" in protocol


def test_protocol_task_keeps_pid_period_and_uart_processing_separate():
    protocol = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    task = re.search(
        r"void binary_protocol_task\(void \*argument\)\s*\{(.*?)\n\}",
        protocol,
        re.DOTALL,
    )
    assert task is not None
    body = task.group(1)
    assert "osKernelGetTickFreq() / CONTROL_UPDATE_FREQ_HZ" in body
    assert "next_wake += control_period_ticks;" in body
    assert "osDelayUntil(next_wake);" in body
    assert "osThreadFlagsWait" not in body


def test_encoder_telemetry_accumulates_timer_deltas_before_transmission():
    encoder = _read(
        "firmware/stm32_chassis/Hiwonder/Peripherals/encoder_motor.c"
    )
    motor_control = _read(
        "firmware/stm32_chassis/Hiwonder/System/motor_control.c"
    )
    docs = _read("docs/communication_protocols.md")
    assert "self->total_count += delta_count" in encoder
    assert "MotorControl_GetRawEncoderCount" in motor_control
    assert "motors[motor_id]->total_count" in motor_control
    assert "cumulative signed left/right output-shaft counts" in docs


def test_status_state_machine_runs_on_control_cadence_not_telemetry_cadence():
    protocol = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    telemetry = re.search(
        r"void binary_protocol_telemetry_task\(void\)\s*\{(.*?)\n\}",
        protocol,
        re.DOTALL,
    )
    assert telemetry is not None
    body = telemetry.group(1)
    status_index = body.index("Status_Update(")
    rate_limit_index = body.index("telemetry_interval_ms")
    assert status_index < rate_limit_index


def test_startup_sea_shanty_is_started_after_buzzer_initialization():
    protocol = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    status = _read(
        "firmware/stm32_chassis/Hiwonder/System/status_integration.c"
    )
    assert protocol.index("buzzers_init();") < protocol.index(
        "Status_PlayStartupSong();"
    )
    assert "startup_song[]" in status
    assert "{880, 8}, {659, 8}, {587, 8}, {554, -4}" in status
    assert "#define STARTUP_SONG_BPM 102U" in status
    assert "STARTUP_SONG_ARTICULATION_MS 12U" in status
    assert "startup_song_start_note();" in status
    assert "buzzer_off(buzzers[0])" in status


def test_buzzer_uses_static_storage_and_single_timer_owner():
    buzzer = _read(
        "firmware/stm32_chassis/Hiwonder/Portings/buzzer_porting.c"
    )
    status = _read(
        "firmware/stm32_chassis/Hiwonder/System/status_integration.c"
    )
    assert "static BuzzerObjectTypeDef buzzer1_object;" in buzzer
    assert "buzzers[0] = &buzzer1_object;" in buzzer
    assert "buzzer_task_handler(buzzers[0], period_ms);" not in status


def test_stm32_flash_helper_is_rock64_only_even_for_build_requests():
    flash = _read("scripts/flash_stm32.sh")
    assert 'if [[ "$(uname -m)" != "aarch64" ]]; then' in flash
    assert 'if [[ "${DO_BUILD}" != true ||' not in flash


def test_battery_priming_consumes_vrefint_without_treating_it_as_a_second_pack():
    battery = _read(
        "firmware/stm32_chassis/Hiwonder/System/battery_integration.c"
    )
    adc = _read("firmware/stm32_chassis/Core/Src/adc.c")
    assert "discard rank 2 (internal VREFINT)" in battery
    assert "current-sense amplifier or second battery ADC" in battery
    assert "sConfig.Channel = ADC_CHANNEL_VREFINT" in adc


def test_uninitialized_battery_cannot_emit_a_false_low_voltage_warning():
    battery = _read(
        "firmware/stm32_chassis/Hiwonder/System/battery_integration.c"
    )
    freertos = _read("firmware/stm32_chassis/Core/Src/freertos.c")
    assert "LOW_VOLTAGE_THRESHOLD_V 10.5f" in battery
    assert "CRITICAL_VOLTAGE_V      9.5f" in battery
    assert "Battery_Update() == 0 && Battery_IsReady()" in freertos


def test_glowy_ultrasonic_uses_the_i2c_expansion_sensor_contract():
    sensor = _read(
        "firmware/stm32_chassis/Hiwonder/System/glowy_ultrasonic.c"
    )
    assert "GLOWY_ULTRASONIC_ADDRESS       0x77U" in sensor
    assert "GLOWY_ULTRASONIC_DISTANCE_REG  0x00U" in sensor
    assert "HAL_I2C_IsDeviceReady(&hi2c2" in sensor
    assert "HAL_I2C_Mem_Read(&hi2c2" in sensor


def test_hc_sr04_owns_shared_exti12_while_imu_is_polled():
    gpio = _read("firmware/stm32_chassis/Core/Src/gpio.c")
    interrupt = _read("firmware/stm32_chassis/Core/Src/stm32f4xx_it.c")
    assert "HC_SR04_TRIG_Pin" in gpio
    assert "GPIO_MODE_IT_RISING_FALLING" in gpio
    assert "HAL_GPIO_EXTI_IRQHandler(HC_SR04_ECHO_Pin)" in interrupt
    assert "GPIO_MODE_IT_RISING;" not in gpio


def test_imu_rate_limited_cycles_reuse_the_last_valid_sample():
    protocol = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    assert "imu_status == -2" in protocol
    assert "protocol_ctx.telemetry.imu.accel_x" in protocol
    assert "protocol_ctx.telemetry.imu.gyro_z" in protocol


def test_imu_sampling_has_one_telemetry_task_owner():
    protocol = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    freertos = _read("firmware/stm32_chassis/Core/Src/freertos.c")
    legacy_porting = _read("firmware/stm32_chassis/Hiwonder/Portings/imu_porting.c")

    assert "int imu_status = IMU_Update(accel, gyro);" in protocol
    assert "generated task also called IMU_Update()" in freertos
    assert "IMU_Update(accel, gyro);" not in freertos
    assert "legacy task previously initialized" in legacy_porting
    assert "imus[0]->update(imus[0]);" not in legacy_porting


def test_imu_startup_verifies_identity_and_retries_bus_failures():
    integration = _read(
        "firmware/stm32_chassis/Hiwonder/System/imu_integration.c"
    )
    assert "QMI8658_WHO_AM_I_REG      0x00U" in integration
    assert "QMI8658_WHO_AM_I_VALUE    0x05U" in integration
    assert "QMI8658_ADDR_LOW          0x6AU" in integration
    assert "QMI8658_ADDR_HIGH         0x6BU" in integration
    assert "IMU_RETRY_PERIOD_MS" in integration
    assert "next_imu_init_attempt" in integration
    assert "imu_initialized = false;" in integration
    assert "IMU_STATUS_UNAVAILABLE" in integration
    assert "HAL_I2C_Mem_Read" in integration
    assert "who_am_i != QMI8658_WHO_AM_I_VALUE" in integration
    assert "QMI8658_CTRL9, 0xA2" not in integration


def test_imu_diagnostics_are_carried_over_the_packed_protocol():
    integration = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    protocol_h = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_packed.h"
    )
    protocol_c = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_packed.c"
    )
    imu = _read("firmware/stm32_chassis/Hiwonder/System/imu_integration.h")
    assert "FUNC_IMU_DIAG          = 0x16" in protocol_h
    assert "IMUDiagnosticsTelemetry" in protocol_h
    assert "IMU_GetDiagnostics(&diagnostics)" in protocol_c
    assert "binary_protocol_send_imu_diagnostics" in integration
    assert "IMU_STATUS_READY" in imu


def test_hc_sr04_protocol_is_distinct_from_reserved_glowy_codes():
    protocol_h = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_packed.h"
    )
    protocol_c = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_packed.c"
    )
    integration = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    assert "FUNC_GLOWY_ULTRASONIC      = 0x14" in protocol_h
    assert "FUNC_GLOWY_ULTRASONIC_DIAG = 0x15" in protocol_h
    assert "FUNC_IMU_DIAG          = 0x16" in protocol_h
    assert "FUNC_HC_SR04_ULTRASONIC = 0x17" in protocol_h
    assert "FUNC_HC_SR04_ULTRASONIC_DIAG = 0x18" in protocol_h
    assert "sizeof(HcSr04UltrasonicTelemetry)" in protocol_c
    assert "binary_protocol_send_hc_sr04_diagnostics" in integration


def test_imu_uses_qmi8658_register_configuration_and_si_scaling():
    """The production wrapper must use the V1.2 QMI8658 register map."""
    integration = _read(
        "firmware/stm32_chassis/Hiwonder/System/imu_integration.c"
    )
    cmake = _read("firmware/stm32_chassis/CMakeLists.txt")
    assert "QMI8658_CTRL2             0x03U" in integration
    assert "QMI8658_CTRL3             0x04U" in integration
    assert "QMI8658_CTRL7             0x08U" in integration
    assert "QMI8658_RESET             0x60U" in integration
    assert "QMI8658_ACCEL_SENSITIVITY 4096.0f" in integration
    assert "QMI8658_GYRO_SENSITIVITY  32.0f" in integration
    assert "HAL_I2C_Mem_Read" in integration
    assert "Hiwonder/Peripherals/imu_mpu6050.c" not in cmake

    freertos = _read("firmware/stm32_chassis/Core/Src/freertos.c")
    ioc = _read("firmware/stm32_chassis/RosRobotControllerM4.ioc")
    assert "imu_data_ready" in freertos
    assert "mpu6050_data_ready" not in freertos
    assert "imu_data_ready,Static" in ioc
    assert "mpu6050_data_ready,Static" not in ioc


def test_host_acceptance_requires_qmi8658_identity_evidence():
    runner = _read(
        "host_ws/src/robot_drivers/robot_drivers/hardware_test_runner.py"
    )
    assert 'values.get("address", "").lower() in {"0x6a", "0x6b"}' in runner
    assert 'values.get("who_am_i", "").lower() == "0x05"' in runner
    assert "return ready and sample_valid and address_valid and identity_valid" in runner


def test_hiwonder_board_profile_preserves_official_conflicts_and_scope():
    """The board facts must not collapse conflicting factory claims."""
    profile = _board_profile()
    assert profile["identity"]["project_board_revision"] == "V1.2"
    assert profile["identity"]["official_documentation_revision_claim"] is None
    sources = {source["id"] for source in profile["official_sources"]}
    assert sources == {
        "product_page",
        "hardware_course",
        "program_analysis",
        "documentation_repository",
    }
    official = profile["official_reference"]
    assert official["board"]["dimensions_mm"] == [85, 60]
    assert official["board"]["max_motor_channels"] == 4
    assert official["board"]["max_motor_current_a"] == 2
    assert official["interfaces"]["imu"]["factory_hardware_label"] == "MPU6050"
    assert official["interfaces"]["imu"]["factory_program_chapter"] == "QMI8658"
    assert official["interfaces"]["buzzer"]["schematic_pin"] == "PA4"
    assert official["interfaces"]["buzzer"]["program_example_pin"] == "PA8"
    assert len(official["power"]["input"]) == 2
    assert official["interfaces"]["pwm_servo"]["power_rails"] == (
        "2 channels on VIN/battery voltage and 2 channels on 5 V"
    )


def test_hiwonder_board_profile_matches_active_ioc_and_production_boundary():
    """Every active board mapping has a checked-in firmware contract."""
    profile = _board_profile()
    project = profile["project_implementation"]
    ioc = _read("firmware/stm32_chassis/RosRobotControllerM4.ioc")
    cmake = _read("firmware/stm32_chassis/CMakeLists.txt")

    host = project["host_link"]
    assert host["peripheral"] == "USART1"
    assert host["pins"] == {"tx": "PA9", "rx": "PA10"}
    assert "PA9.Signal=USART1_TX" in ioc
    assert "PA10.Signal=USART1_RX" in ioc
    assert "ROCK64_HOST_UART_HANDLE huart1" in _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )

    imu = project["imu"]
    assert imu["driver_assumption"] == "QMI8658"
    assert imu["pins"] == {
        "scl": "PB10",
        "sda": "PB11",
        "interrupt_input": "PB12",
    }
    assert "PB10.Signal=I2C2_SCL" in ioc
    assert "PB11.Signal=I2C2_SDA" in ioc
    assert "PB12.Signal=GPIO_Input" in ioc
    assert "I2C2.ClockSpeed=400000" in ioc
    assert "Hiwonder/Peripherals/imu_mpu6050.c" not in cmake
    assert "Hiwonder/System/imu_integration.c" in cmake

    pin_map = project["active_pin_map"]
    expected_ioc_signals = {
        "battery_adc": "PB0.Signal=ADCx_IN8",
        "buzzer": "PA8.Signal=GPIO_Output",
        "status_led": "PE10.Signal=GPIO_Output",
        "debug_swdio": "PA13.Signal=SYS_JTMS-SWDIO",
    }
    for signal in expected_ioc_signals.values():
        assert signal in ioc
    assert pin_map["buttons"] == {"key_1": "PE1", "key_2": "PE0"}
    assert "PE0.Signal=GPIO_Input" in ioc
    assert "PE1.Signal=GPIO_Input" in ioc
    assert pin_map["usb_host"] == {"dm": "PB14", "dp": "PB15"}
    assert "PB14.Signal=USB_OTG_HS_DM" in ioc
    assert "PB15.Signal=USB_OTG_HS_DP" in ioc

    assert pin_map["factory_reference_uart"] == {
        "peripheral": "USART3",
        "tx": "PD8",
        "rx": "PD9",
        "project_role": "not production host transport",
    }
    assert "PD8.Signal=USART3_TX" in ioc
    assert "PD9.Signal=USART3_RX" in ioc
    assert project["commissioned_scope"]["physical_drive_motors"] == 2
    assert project["commissioned_scope"]["optional_glowy_i2c_sensor"][
        "enabled_in_basic_profile"
    ] is False


def test_hiwonder_board_profile_covers_the_complete_active_io_surface():
    """Every claimed active board route must exist in IOC and generated HAL."""
    profile = _board_profile()["project_implementation"]
    ioc = _read("firmware/stm32_chassis/RosRobotControllerM4.ioc")
    gpio = _read("firmware/stm32_chassis/Core/Src/gpio.c")
    i2c = _read("firmware/stm32_chassis/Core/Src/i2c.c")
    spi = _read("firmware/stm32_chassis/Core/Src/spi.c")
    usart = _read("firmware/stm32_chassis/Core/Src/usart.c")
    tim = _read("firmware/stm32_chassis/Core/Src/tim.c")
    motor = _read("firmware/stm32_chassis/Hiwonder/Portings/motor_porting.c")
    motor_control = _read(
        "firmware/stm32_chassis/Hiwonder/System/motor_control.c"
    )
    pin_map = profile["active_pin_map"]

    assert pin_map["display"] == {
        "sck": "PB13",
        "mosi": "PC3",
        "blk": "PD11",
        "cs": "PD12",
        "dc": "PD13",
        "res": "PD14",
    }
    assert pin_map["bus_servo"] == {
        "tx": "PC6",
        "rx": "PC7",
        "tx_enable": "PE7",
        "rx_enable": "PE8",
    }
    assert pin_map["sbus"] == {"rx": "PD2", "unused_tx": "PC12"}
    assert pin_map["usb_host"] == {"dm": "PB14", "dp": "PB15"}
    assert pin_map["auxiliary_uart"] == {
        "peripheral": "USART2",
        "tx": "PD5",
        "rx": "PD6",
    }
    assert pin_map["battery_adc"] == "PB0"
    assert pin_map["buzzer"] == "PA8"
    assert pin_map["status_led"] == "PE10"
    assert pin_map["buttons"] == {"key_1": "PE1", "key_2": "PE0"}
    assert pin_map["debug"] == {"swdio": "PA13", "swclk": "PA14"}

    assert profile["clock"] == {
        "hse_hz": 8000000,
        "system_clock_hz": 168000000,
        "source": "IOC RCC.HSE_VALUE and generated SystemClock_Config",
    }
    assert "RCC.HSE_VALUE=8000000" in ioc
    assert "RCC.SYSCLKFreq_VALUE=168000000" in ioc
    assert "External 8MHz crystal" in _read("docs/robot_hardware_reference.md")
    assert "External 25MHz crystal" not in _read(
        "docs/robot_hardware_reference.md"
    )

    ioc_signals = {
        "PA8": "GPIO_Output",
        "PA9": "USART1_TX",
        "PA10": "USART1_RX",
        "PA11": "GPIO_Output",
        "PB0": "ADCx_IN8",
        "PB10": "I2C2_SCL",
        "PB11": "I2C2_SDA",
        "PB12": "GPIO_Input",
        "PB13": "SPI2_SCK",
        "PB14": "USB_OTG_HS_DM",
        "PB15": "USB_OTG_HS_DP",
        "PC3": "SPI2_MOSI",
        "PC6": "USART6_TX",
        "PC7": "USART6_RX",
        "PD2": "UART5_RX",
        "PD5": "USART2_TX",
        "PD6": "USART2_RX",
        "PD8": "USART3_TX",
        "PD9": "USART3_RX",
        "PD11": "GPIO_Output",
        "PD12": "GPIO_Output",
        "PD13": "GPIO_Output",
        "PD14": "GPIO_Output",
        "PE0": "GPIO_Input",
        "PE1": "GPIO_Input",
        "PE7": "GPIO_Output",
        "PE8": "GPIO_Output",
        "PE10": "GPIO_Output",
        "PE9": "S_TIM1_CH1",
        "PE11": "S_TIM1_CH2",
        "PE13": "S_TIM1_CH3",
        "PE14": "S_TIM1_CH4",
        "PE5": "S_TIM9_CH1",
        "PE6": "S_TIM9_CH2",
        "PB8": "S_TIM10_CH1",
        "PA0-WKUP": "S_TIM5_CH1",
        "PA1": "S_TIM5_CH2",
        "PA15": "S_TIM2_CH1_ETR",
        "PB3": "S_TIM2_CH2",
        "PB4": "S_TIM3_CH1",
        "PB5": "S_TIM3_CH2",
        "PB6": "S_TIM4_CH1",
        "PB7": "S_TIM4_CH2",
    }
    for pin, signal in ioc_signals.items():
        assert f"{pin}.Signal={signal}" in ioc, (pin, signal)

    assert "hi2c2.Init.ClockSpeed = 400000" in i2c
    assert "GPIO_PIN_10|GPIO_PIN_11" in i2c
    assert "GPIO_AF4_I2C2" in i2c
    assert "GPIO_PIN_3" in spi and "GPIO_PIN_13" in spi
    assert "GPIO_AF5_SPI2" in spi
    for baud in ("100000", "1000000", "9600", "115200"):
        assert f"Init.BaudRate = {baud}" in usart
    assert "huart5.Init.WordLength = UART_WORDLENGTH_9B" in usart
    assert "huart5.Init.Parity = UART_PARITY_EVEN" in usart
    assert "huart5.Init.StopBits = UART_STOPBITS_2" in usart
    assert "huart5.Init.Mode = UART_MODE_RX" in usart

    assert "GPIO_PIN_15" in tim and "GPIO_AF1_TIM2" in tim
    assert "GPIO_PIN_4|GPIO_PIN_5" in tim and "GPIO_AF2_TIM3" in tim
    assert "GPIO_PIN_6|GPIO_PIN_7" in tim and "GPIO_AF2_TIM4" in tim
    assert "GPIO_PIN_0|GPIO_PIN_1" in tim and "GPIO_AF2_TIM5" in tim
    assert "TIM1_CH1_Pin|TIM1_CH2_Pin|TIM1_CH3_Pin|TIM1_CH4_Pin" in tim
    assert "GPIO_PIN_5|GPIO_PIN_6" in tim and "GPIO_AF3_TIM9" in tim
    assert "GPIO_PIN_8" in tim and "GPIO_AF3_TIM10" in tim

    # TIM11 exists as a legacy/future timer object, but the active image does
    # not route PB9 to it. This distinction prevents a false four-motor claim.
    post_init = tim.split("void HAL_TIM_MspPostInit", 1)[1].split(
        "void HAL_TIM_Base_MspDeInit", 1
    )[0]
    assert "TIM11" not in post_init
    assert "GPIO_PIN_1|GPIO_PIN_2|GPIO_PIN_9" in gpio
    assert "HAL_GPIO_Init(GPIOB" in gpio

    expected_motor_timers = {
        0: "encoder_timer = &htim2",
        1: "encoder_timer = &htim5",
        2: "encoder_timer = &htim4",
        3: "encoder_timer = &htim3",
    }
    for motor_id, route in expected_motor_timers.items():
        assert f"case {motor_id}: {route}" in motor_control
    assert "motor1_set_pulse" in motor and "TIM_CHANNEL_1" in motor
    assert "motor2_set_pulse" in motor and "TIM_CHANNEL_3" in motor
    assert "speed = -speed" in motor
    assert "current_encoder =" in motor_control
    assert "motors[i]->ticks_overflow - current_encoder" in motor_control

    active_pwm = profile["active_pin_map"]["project_configured_motor_pwm"]
    assert active_pwm["motor_4"] == ["PB8"]
    assert "PB9/TIM11" in active_pwm["motor_4_missing_channel"]


def test_board_audit_docs_link_machine_profile_and_state_source_conflicts():
    """Agent-facing docs must point to the same conflict-aware authority."""
    audit = _read("docs/HIWONDER_ROS_ROBOT_CONTROLLER_V1_2.md")
    reference = _read("docs/robot_hardware_reference.md")
    source = _read("docs/SOURCE_OF_TRUTH_1_0.md")
    assert "hiwonder_ros_robot_controller_v1_2_profile.json" in audit
    assert "MPU6050" in audit and "QMI8658" in audit
    assert "PA4" in audit and "PA8" in audit
    assert "serial port 2" in audit
    assert "USART1 PA9/PA10" in audit
    assert "HIWONDER_ROS_ROBOT_CONTROLLER_V1_2.md" in reference
    assert "not an unambiguous official V1.2 claim" in reference
    assert "Physical identity is accepted only by this runtime proof" in source


def test_imu_reset_and_reads_check_i2c_return_values():
    integration = _read(
        "firmware/stm32_chassis/Hiwonder/System/imu_integration.c"
    )
    assert "qmi8658_write_checked(QMI8658_RESET, 0xB0)" in integration
    assert "qmi8658_write_checked(QMI8658_CTRL7, 0x03)" in integration
    assert "qmi8658_read_checked(QMI8658_ACCEL_X_L, sensor_data" in integration
    assert "== HAL_OK ? 0 : -1" in integration
    assert "imu_error_count++" in integration
    assert "!imu_initialized || temp == NULL" in integration


def test_basic_hardware_profile_keeps_i2c2_for_the_onboard_imu_only():
    i2c = _read("firmware/stm32_chassis/Core/Src/i2c.c")
    ioc = _read("firmware/stm32_chassis/RosRobotControllerM4.ioc")
    integration = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    assert "hi2c2.Init.ClockSpeed = 400000" in i2c
    assert "I2C2.I2C_Mode=I2C_Fast" in ioc
    assert "hc_sr04_init();" in integration
    assert "binary_protocol_send_hc_sr04_diagnostics" in integration


def test_hc_sr04_uses_the_board_header_pin_contract():
    main_h = _read("firmware/stm32_chassis/Core/Inc/main.h")
    ioc = _read("firmware/stm32_chassis/RosRobotControllerM4.ioc")
    pins_csv = _read("firmware/stm32_chassis/stm32pinscustom.csv")
    sensor = _read("firmware/stm32_chassis/Hiwonder/System/hc_sr04.c")
    gpio = _read("firmware/stm32_chassis/Core/Src/gpio.c")
    servo_port = _read(
        "firmware/stm32_chassis/Hiwonder/Portings/pwm_servo_porting.c"
    )
    assert "#define HC_SR04_TRIG_Pin GPIO_PIN_8" in main_h
    assert "#define HC_SR04_ECHO_Pin GPIO_PIN_12" in main_h
    assert "PC10/PC11" not in main_h
    assert "PC10" not in ioc
    assert "PC11" not in ioc
    assert "PWM_SERVO_2_Pin" not in main_h
    assert "PWM_SERVO_3_Pin" not in main_h
    assert "PA12.GPIO_Label=HC_SR04_ECHO" in ioc
    assert "PB12.Signal=GPIO_Input" in ioc
    assert "PC8.Signal=GPIO_Output" in ioc
    assert "PA12.Signal=GPIO_EXTI12" in ioc
    assert "PA12.GPIO_PuPd=GPIO_NOPULL" in ioc
    assert '"65","PC8","Output","GPIO_Output","HC_SR04_TRIG"' in pins_csv
    assert '"71","PA12","I/O","GPIO_EXTI12","HC_SR04_ECHO"' in pins_csv
    assert "Hiwonder/System/hc_sr04.c" in _read(
        "firmware/stm32_chassis/CMakeLists.txt"
    )
    assert "HC_SR04_MIN_ECHO_US 117U" in sensor
    assert "HC_SR04_MAX_ECHO_US 23323U" in sensor
    assert "GPIO_NOPULL" in gpio
    assert "HAL_GPIO_WritePin" in servo_port  # J1 remains the live output
    for channel in (2, 3, 4):
        body = re.search(
            rf"pwm_servo{channel}_write_pin\(uint32_t new_state\)"
            rf"\s*\{{(.*?)\n\}}",
            servo_port,
            re.DOTALL,
        )
        assert body is not None
        assert "HAL_GPIO_WritePin" not in body.group(1)


def test_jgb3865_520r45_encoder_contract_is_45_to_1_across_stack():
    motors = _read("firmware/stm32_chassis/Hiwonder/Portings/motors_param.h")
    bridge = _read(
        "host_ws/src/robot_drivers/robot_drivers/stm32_hardened_bridge.py"
    )
    hardware = _read("host_ws/src/robot_bringup/config/rock64_hardware.yaml")
    teleop = _read("host_ws/src/robot_teleop/robot_teleop/ps5_ros_bridge.py")

    assert "#define MOTOR_JGB520_TICKS_PER_CIRCLE 1980.0f" in motors
    assert "#define MOTOR_DEFAULT_TICKS_PER_CIRCLE 1980.0f" in motors
    assert '"encoder_ticks_per_rev", 1980' in bridge
    assert "encoder_ticks_per_rev: 1980" in hardware
    assert '"encoder_ticks_per_rev", 1980' in teleop
