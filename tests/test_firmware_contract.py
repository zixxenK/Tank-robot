"""Static contracts for firmware safety integrations that need hardware proof."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


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


def test_glowy_ultrasonic_does_not_claim_legacy_pulse_pins():
    gpio = _read("firmware/stm32_chassis/Core/Src/gpio.c")
    interrupt = _read("firmware/stm32_chassis/Core/Src/stm32f4xx_it.c")
    assert "GPIO_MODE_IT_RISING_FALLING" not in gpio
    assert "HAL_GPIO_EXTI_IRQHandler" not in interrupt


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
    assert "MPU6050_WHO_AM_I" in integration
    assert "MPU6050_DEV_ADDR_1" in integration
    assert "MPU6050_DEV_ADDR_2" in integration
    assert "IMU_RETRY_PERIOD_MS" in integration
    assert "next_imu_init_attempt" in integration
    assert "imu_initialized = false;" in integration
    assert "IMU_STATUS_UNAVAILABLE" in integration
    assert "HAL_I2C_Mem_Read" in integration
    assert "imu_identity_is_supported" in integration


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


def test_imu_accepts_known_mpu_family_identity_values():
    """Known MPU-family identities remain explicitly checked."""
    header = _read(
        "firmware/stm32_chassis/Hiwonder/Peripherals/imu_mpu6050.h"
    )
    integration = _read(
        "firmware/stm32_chassis/Hiwonder/System/imu_integration.c"
    )
    for value in (
        "MPU6050_WHO_AM_I_MPU6500",
        "MPU6050_WHO_AM_I_MPU9250",
        "MPU6050_WHO_AM_I_MPU9255",
    ):
        assert value in header
        assert value in integration


def test_imu_reset_and_reads_check_i2c_return_values():
    driver = _read(
        "firmware/stm32_chassis/Hiwonder/Peripherals/imu_mpu6050.c"
    )
    integration = _read(
        "firmware/stm32_chassis/Hiwonder/System/imu_integration.c"
    )
    assert "int mpu6050_reset(MPU6050ObjectTypeDef *self)" in driver
    assert "mpu6050_reset(&imu_sensor) != 0" in integration
    assert "!= HAL_OK" in integration
    assert "imu_error_count++" in integration


def test_basic_hardware_profile_keeps_i2c2_for_the_onboard_imu_only():
    i2c = _read("firmware/stm32_chassis/Core/Src/i2c.c")
    ioc = _read("firmware/stm32_chassis/RosRobotControllerM4.ioc")
    integration = _read(
        "firmware/stm32_chassis/Hiwonder/System/"
        "uart_binary_protocol_integration_packed.c"
    )
    assert "hi2c2.Init.ClockSpeed = 100000" in i2c
    assert "I2C2.I2C_Mode=I2C_Standard" in ioc
    assert "#define ENABLE_GLOWY_BASIC_PROFILE 0" in integration


def test_legacy_secondary_servo_pads_are_inert_for_i2c_sensor_use():
    main_h = _read("firmware/stm32_chassis/Core/Inc/main.h")
    ioc = _read("firmware/stm32_chassis/RosRobotControllerM4.ioc")
    pins_csv = _read("firmware/stm32_chassis/stm32pinscustom.csv")
    servo_port = _read(
        "firmware/stm32_chassis/Hiwonder/Portings/pwm_servo_porting.c"
    )
    assert "HC_" not in main_h
    assert "PC10/PC11" not in main_h
    assert "PC10" not in ioc
    assert "PC11" not in ioc
    assert "PWM_SERVO_2_Pin" not in main_h
    assert "PWM_SERVO_3_Pin" not in main_h
    assert "PA12.GPIO_Label=UNUSED_PA12" in ioc
    assert "PB12.Signal=GPIO_Input" in ioc
    assert "PC8.Signal=GPIO_Analog" in ioc
    assert "PA12.Signal=GPIO_Analog" in ioc
    assert '"65","PC8","Analog","GPIO_Analog","UNUSED_PC8"' in pins_csv
    assert '"71","PA12","Analog","GPIO_Analog","UNUSED_PA12"' in pins_csv
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
