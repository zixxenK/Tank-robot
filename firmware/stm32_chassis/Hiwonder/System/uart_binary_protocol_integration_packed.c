/**
 * @file uart_binary_protocol_integration_packed.c
 * @brief Production integration example for packed binary protocol
 *
 * This file integrates the packed binary protocol with:
 * 1. The board WCH USB-to-UART connector for Rock64 communication
 * 2. HAL tick based command timeout
 * 3. Actual motor control
 *
 * HARDWARE CONFIGURATION:
 * - The product-labeled UART1 USB-C link is USART1 (PA9/PA10) at 1000000 8N1.
 * - USART3 (PD8/PD9) remains the separate factory MASTER pair.
 * - USART2 (PD5/PD6) is the auxiliary/Bluetooth port.
 * - ST-Link remains SWD-only.
 * - TIM2/TIM3/TIM4/TIM5: factory quadrature encoder inputs; never
 *   reconfigured here.
 */

#include "uart_binary_protocol_packed.h"
#include "motor_control.h"
#include "motors_param.h"
#include "imu_integration.h"
#include "battery_integration.h"
#include "status_integration.h"
#include "hc_sr04.h"
#include "sg90_servo.h"
#include "watchdog.h"
#include "buzzer.h"
#include "main.h"
#include "usart.h"
#include "dma.h"
#include "tim.h"
#include "cmsis_os2.h"
#include <math.h>
#include <string.h>

/* Production host link: physical UART1 -> USART1 on PA9/PA10. */
#define ROCK64_HOST_UART_HANDLE huart1
#define ROCK64_HOST_DMA_RX_HANDLE hdma_usart1_rx
extern DMA_HandleTypeDef hdma_usart1_rx;

// ============================================================================
// PROTOCOL CONTEXT (Global for interrupt access)
// ============================================================================

static BinaryProtocolContext protocol_ctx;
static osThreadId_t protocol_task_handle;

extern BuzzerObjectTypeDef *buzzers[1];
extern void buzzers_init(void);

#define PROTOCOL_RX_EVENT_FLAG (1U << 0)

void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t size) {
    if (huart != &ROCK64_HOST_UART_HANDLE) {
        return;
    }

    binary_protocol_rx_event(&protocol_ctx, size);
    if (protocol_task_handle != NULL) {
        (void)osThreadFlagsSet(protocol_task_handle, PROTOCOL_RX_EVENT_FLAG);
    }
}

// ============================================================================
// INTEGRATION INITIALIZATION
// ============================================================================

void binary_protocol_integration_init_packed(void) {
    /* Status is useful for the board indicators, but battery ADC startup is
     * deliberately not part of the motor-link bring-up.  On this integrated
     * controller the ADC/VREF path is board-specific and the old priming code
     * can fault before USART1 and the motor controller are alive.  Battery
     * monitoring is not a prerequisite for this raised-track bench test; the
     * host receives an unavailable value instead of a fabricated reading. */
    /* Initialize the real buzzer instance before protocol commands can
     * arrive. Status beeps reuse this same hardware object. */
    buzzers_init();
    (void)Status_Init();

    if (!Watchdog_Init() || Watchdog_WasReset()) {
        /* A previous IWDG reset is useful diagnostic information, but does
         * not prevent the motor link from recovering after a clean reboot. */
        Status_SetLEDWarning();
    }

    // Initialize motor control layer first. Startup PWM values are explicitly
    // cleared below so merely booting the image cannot request motion.
    MotorControl_Init();

    MotorControl_EmergencyStop();
    hc_sr04_init();
    SG90Servo_Init();

    /* Sensor bring-up is non-fatal: the protocol remains available when an
     * IMU is absent, but a ready MPU6050 contributes real telemetry. */
    if (IMU_Init() != 0) {
        Status_SetLEDWarning();
    }

    /* Use the production WCH Rock64 host link on USART1 PA9/PA10. Telemetry TX
     * deliberately uses
     * bounded blocking
     * writes: frames are short at 1 Mbaud, and this removes a second DMA
     * completion path from the motor bring-up image. */
    binary_protocol_init_packed(&protocol_ctx,
                                &ROCK64_HOST_UART_HANDLE,
                                &ROCK64_HOST_DMA_RX_HANDLE,
                                NULL,
                                250,               // 250ms command timeout
                                0);                // heartbeat not required
    protocol_ctx.heartbeat_required = false;
}

// ============================================================================
// UART BUFFER PROCESSING (Call from the protocol task)
// ============================================================================

void binary_protocol_process_dma_buffer(void) {
    /* Consume the selected host USART HAL idle-DMA ring. */
    binary_protocol_process_dma(&protocol_ctx);
}

// ============================================================================
// MAIN LOOP TASK (Call from main() or FreeRTOS task)
// ============================================================================

void binary_protocol_main_task(void) {
    binary_protocol_process_dma_buffer();
    
    // Check for timeouts
    if (binary_protocol_check_timeouts(&protocol_ctx) ||
        protocol_ctx.emergency_stop_active) {
        MotorControl_EmergencyStop();
    }
    
    // Process motor commands. The wire value is normalized to [-1, 1] and is
    // converted to the configured motor limit, not an arbitrary 10 RPS.
    MotorCommandEntry motor_commands[MOTOR_COMMAND_CAPACITY];
    uint8_t motor_count = binary_protocol_get_motor_commands(&protocol_ctx,
                                                             motor_commands,
                                                             MOTOR_COMMAND_CAPACITY);
    
    if (motor_count > 0) {
        // Apply motor commands using our motor control layer
        // This uses Hiwonder's existing PID control system
        for (uint8_t i = 0; i < motor_count; i++) {
            uint8_t motor_id = motor_commands[i].motor_id;
            float rps = motor_commands[i].rps;
            
            float actual_rps = rps * MOTOR_DEFAULT_RPS_LIMIT;
            
            // Set target RPS for the motor
            MotorControl_SetTargetRPS(motor_id, actual_rps);
        }
    }
    
    // Update motor control loop (100Hz PID control)
    MotorControl_Update(CONTROL_PERIOD_SEC);
    
}

// ============================================================================
// TELEMETRY UPDATE AND TRANSMISSION
// ============================================================================

void binary_protocol_telemetry_task(void) {
    uint32_t now = HAL_GetTick();
    if ((now - protocol_ctx.last_telemetry_time) <
        protocol_ctx.telemetry_interval_ms) {
        return;
    }
    protocol_ctx.last_telemetry_time = now;

    // Read encoder values from motor control layer
    int32_t left_encoder = MotorControl_GetEncoderCount(0);   // Motor 0 (left)
    int32_t right_encoder = MotorControl_GetEncoderCount(1);  // Motor 1 (right)
    
    /* Battery monitoring is intentionally unavailable in the motor-only
     * bring-up image.  Do not call the ADC path or turn an absent reading into
     * a low-battery motor inhibit. */
    float battery_voltage = NAN;
    float battery_current = NAN;
    
    // Read IMU data with fixed delta time (rate-limited to 50Hz)
    float accel[3], gyro[3];
    int imu_status = IMU_Update(accel, gyro);
    
    float accel_x = 0.0f, accel_y = 0.0f, accel_z = 0.0f;
    float gyro_x = 0.0f, gyro_y = 0.0f, gyro_z = 0.0f;
    
    if (imu_status == 0) {
        // IMU read successful
        accel_x = accel[0];
        accel_y = accel[1];
        accel_z = accel[2];
        gyro_x = gyro[0];
        gyro_y = gyro[1];
        gyro_z = gyro[2];
        
        // Normal operation indicator
        Status_SetLEDNormal();
    } else if (imu_status == -2) {
        /* Not time yet (rate limiting): retain the last valid sample.  The
         * telemetry task runs faster than the IMU's 50 Hz acquisition rate;
         * publishing the zero-initialized locals here would make the host
         * topic alternate between real data and placeholders. */
        accel_x = protocol_ctx.telemetry.imu.accel_x;
        accel_y = protocol_ctx.telemetry.imu.accel_y;
        accel_z = protocol_ctx.telemetry.imu.accel_z;
        gyro_x = protocol_ctx.telemetry.imu.gyro_x;
        gyro_y = protocol_ctx.telemetry.imu.gyro_y;
        gyro_z = protocol_ctx.telemetry.imu.gyro_z;
    } else {
        // IMU error occurred
        Status_SetLEDWarning();
    }
    
    // Update telemetry structure
    binary_protocol_update_telemetry(&protocol_ctx,
                                     left_encoder,
                                     right_encoder,
                                     battery_voltage,
                                     battery_current,
                                     accel_x, accel_y, accel_z,
                                     gyro_x, gyro_y, gyro_z);

    HcSr04Measurement ultrasonic;
    /* Consume a completed echo before starting the next trigger.  If this
     * task was delayed for more than the normal 20 ms cadence, servicing
     * first could otherwise replace an unread measurement. */
    bool ultrasonic_ready = hc_sr04_get_measurement(&ultrasonic);
    hc_sr04_service();
    if (ultrasonic_ready) {
        protocol_ctx.telemetry.ultrasonic.distance_mm = ultrasonic.distance_mm;
        protocol_ctx.telemetry.ultrasonic.echo_us = ultrasonic.echo_us;
        protocol_ctx.telemetry.ultrasonic.valid = ultrasonic.valid ? 1U : 0U;
        protocol_ctx.telemetry.ultrasonic.reserved = hc_sr04_get_status();
    } else {
        /* Do not carry a previous measurement into a timeout/no-echo frame.
         * The validity flag is authoritative, but zeroing the payload keeps
         * diagnostics and downstream consumers from mistaking stale values
         * for the current cycle. */
        protocol_ctx.telemetry.ultrasonic.distance_mm = 0U;
        protocol_ctx.telemetry.ultrasonic.echo_us = 0U;
        protocol_ctx.telemetry.ultrasonic.valid = 0U;
        protocol_ctx.telemetry.ultrasonic.reserved = hc_sr04_get_status();
    }
    
    // Send telemetry burst
    binary_protocol_send_telemetry_burst(&protocol_ctx);
    
    /* The protocol task runs the motor loop at CONTROL_PERIOD_SEC. Give the
     * buzzer state machine the same elapsed period instead of relying on a
     * second application task that is not present in this image. */
    Status_Update((uint32_t)(CONTROL_PERIOD_SEC * 1000.0f));
}

// ============================================================================
// ============================================================================

// ============================================================================
// EMERGENCY STOP (External trigger)
// ============================================================================

void binary_protocol_trigger_emergency_stop(void) {
    binary_protocol_emergency_stop(&protocol_ctx);
    
    // Trigger emergency indication
    Status_EmergencyBeep();
    Status_SetLEDEmergency();
    
    // Stop motors via motor control layer
    MotorControl_EmergencyStop();
}

// ============================================================================
// FREERTOS TASK (If using RTOS)
// ============================================================================

void binary_protocol_task(void *argument) {
    (void)argument;

    protocol_task_handle = osThreadGetId();
    binary_protocol_integration_init_packed();

    for (;;) {
        binary_protocol_main_task();
        binary_protocol_telemetry_task();
        Watchdog_Refresh();

        /* The idle-DMA callback wakes this task immediately after a burst;
         * the timeout keeps the motor watchdog/PID loop alive when the link
         * is quiet. */
        (void)osThreadFlagsWait(PROTOCOL_RX_EVENT_FLAG,
                                osFlagsWaitAny,
                                1U);
    }
}

// ============================================================================
// MAIN LOOP INTEGRATION (If not using RTOS)
// ============================================================================

#ifndef USE_FREERTOS

/**
 * @brief Call this from your main() while loop
 * Example:
 *
 * int main(void) {
 *     HAL_Init();
 *     SystemClock_Config();
 *     MX_GPIO_Init();
 *     MX_DMA_Init();
 *     MX_TIM2_Init();
 *
 *     binary_protocol_integration_init_packed();
 *
 *     while (1) {
 *         binary_protocol_main_task();
 *         HAL_Delay(10);  // 10ms loop
 *     }
 * }
 */

#endif // !USE_FREERTOS

// ============================================================================
// DIAGNOSTICS
// ============================================================================

/**
 * @brief Get protocol statistics for debugging
 */
const void* binary_protocol_get_diagnostics(void) {
    return binary_protocol_get_stats(&protocol_ctx);
}

/**
 * @brief Reset protocol statistics
 */
void binary_protocol_reset_diagnostics(void) {
    memset(&protocol_ctx.stats, 0, sizeof(protocol_ctx.stats));
}
