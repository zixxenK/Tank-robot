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
 * - The original Rock64 link is USART1 (PA9/PA10) at 1000000 8N1.
 * - USART2 (PD5/PD6) is the auxiliary/Bluetooth port.
 * - PB14/PB15 are the board USB host port, not the Rock64 motor link.
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
#include "main.h"
#include "usart.h"
#include "dma.h"
#include "tim.h"
#include <math.h>
#include <string.h>

// ============================================================================
// PROTOCOL CONTEXT (Global for interrupt access)
// ============================================================================

static BinaryProtocolContext protocol_ctx;
extern DMA_HandleTypeDef hdma_usart1_rx;

// ============================================================================
// INTEGRATION INITIALIZATION
// ============================================================================

void binary_protocol_integration_init_packed(void) {
    /* These services are required before telemetry can be produced. The
     * safety gateway deliberately refuses motion without valid battery data. */
    (void)Status_Init();
    (void)Battery_Init();

    // Initialize motor control layer first. Startup PWM values are explicitly
    // cleared below so merely booting the image cannot request motion.
    MotorControl_Init();

    MotorControl_EmergencyStop();

    /* Use the original Rock64 UART. The WCH USB-serial bridge is physically
     * wired to PA9/PA10 (USART1). RX uses the factory circular DMA;
     * TX is deliberately polled so it does not depend on a DMA IRQ that is
     * not required by the motor safety loop. */
    binary_protocol_init_packed(&protocol_ctx,
                               &huart1,
                               &hdma_usart1_rx,
                               NULL,
                               250,               // 250ms command timeout
                               0);                // heartbeat not required
    protocol_ctx.heartbeat_required = false;
}

// ============================================================================
// UART BUFFER PROCESSING (Call from the protocol task)
// ============================================================================

void binary_protocol_process_dma_buffer(void) {
    /* Consume the USART1 circular-DMA buffer. Do not poll USART2/USART3:
     * they are the debug/auxiliary ports and probing them can steal bytes or leave
     * HAL UART state busy. */
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
    
    // Read battery voltage from integration layer
    Battery_Update();  // Process ADC DMA buffer
    float battery_voltage = Battery_GetVoltage();
    float battery_current = Battery_IsCurrentValid() ? Battery_GetCurrent() : NAN;
    
    // Check for low battery condition
    if (Battery_IsLowVoltage()) {
        Status_LowBatteryBeep();
        Status_SetLEDWarning();
    }
    
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
        // Not time yet (rate limiting) - use last valid values
        // This is normal behavior, not an error
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
    
    // Send telemetry burst
    binary_protocol_send_telemetry_burst(&protocol_ctx);
    
    Status_Update(20);
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

#ifdef USE_FREERTOS

void binary_protocol_task(void *argument) {
    (void)argument;
    
    binary_protocol_integration_init_packed();
    
    for (;;) {
        binary_protocol_main_task();
        
        // 10ms task period = 100Hz
        osDelay(10);
    }
}

#endif // USE_FREERTOS

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
