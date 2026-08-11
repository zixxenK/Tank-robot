/**
 * @file uart_binary_protocol_integration_packed.c
 * @brief Production integration example for packed binary protocol
 *
 * This file integrates the packed binary protocol with:
 * 1. DMA circular reception on USART1
 * 2. HAL tick based command and heartbeat timeouts
 * 3. FreeRTOS task integration
 * 4. Actual motor control
 *
 * HARDWARE CONFIGURATION:
 * - USART1: Rock64 host link at 115200 baud (PA9=DBG_TX, PA10=DBG_RX) - factory config
 * - TIM2: Motor 2 quadrature encoder; never reconfigured here
 */

#include "uart_binary_protocol_packed.h"
#include "motor_control.h"
#include "encoder_motor.h"
#include "adc.h"
#include "imu_mpu6050.h"
#include "imu_integration.h"
#include "battery_integration.h"
#include "status_integration.h"
#include "watchdog.h"
#include "main.h"
#include "usart.h"
#include "tim.h"
#include <string.h>
#include <math.h>

extern DMA_HandleTypeDef hdma_usart2_rx;
extern DMA_HandleTypeDef hdma_usart2_tx;
extern DMA_HandleTypeDef hdma_usart3_rx;
extern DMA_HandleTypeDef hdma_usart3_tx;

extern UART_HandleTypeDef huart1;  // USART1 for Rock64 host link (PA9/PA10) - factory config

// ============================================================================
// PROTOCOL CONTEXT (Global for interrupt access)
// ============================================================================

static BinaryProtocolContext protocol_ctx;

// ============================================================================
// INTEGRATION INITIALIZATION
// ============================================================================

void binary_protocol_integration_init_packed(void) {
    // Initialize motor control layer first
    MotorControl_Init();
    
    // Initialize IMU with fixed delta time (50Hz)
    IMU_Init();
    
    // Initialize battery monitoring with filter priming
    Battery_Init();
    
    // Initialize status peripherals (buzzer/LED)
    Status_Init();
    
    // Execute startup indication sequence
    Status_StartupSequence();
    
    // Initialize protocol with packed structures
    // Using USART1 (PA9/PA10) without DMA for Rock64 host link at 115200 baud (factory config)
    // Note: USART1 doesn't have DMA in factory config, so protocol will use polling mode
    binary_protocol_init_packed(&protocol_ctx,
                               &huart1,           // USART1 for Rock64 host link (PA9/PA10)
                               NULL,              // No DMA for USART1 RX (factory config)
                               NULL,              // No DMA for USART1 TX (factory config)
                               200,               // 200ms command timeout
                               500);              // 500ms heartbeat timeout

    Watchdog_Init();
}

// ============================================================================
// DMA BUFFER PROCESSING (Call from main loop)
// ============================================================================

void binary_protocol_process_dma_buffer(void) {
    binary_protocol_process_dma(&protocol_ctx);
}

// ============================================================================
// MAIN LOOP TASK (Call from main() or FreeRTOS task)
// ============================================================================

void binary_protocol_main_task(void) {
    // Process incoming DMA data
    binary_protocol_process_dma_buffer();
    
    // Check for timeouts
    if (binary_protocol_check_timeouts(&protocol_ctx) ||
        protocol_ctx.emergency_stop_active) {
        MotorControl_EmergencyStop();
    }
    
    // Process motor commands
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
            
            // Convert normalized RPS (-1.0 to 1.0) to actual RPS
            // Assuming max motor RPS of 10.0 (adjust based on your motors)
            float actual_rps = rps * 10.0f;
            
            // Set target RPS for the motor
            MotorControl_SetTargetRPS(motor_id, actual_rps);
        }
    }
    
    // Update motor control loop (100Hz PID control)
    MotorControl_Update(CONTROL_PERIOD_SEC);
    
    Watchdog_Refresh();
}

// ============================================================================
// TELEMETRY UPDATE AND TRANSMISSION
// ============================================================================

void binary_protocol_telemetry_task(void) {
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
    
    // Emit liveness independently of inbound parser activity so the host can
    // verify the serial TX path even when commands or heartbeat pings are absent.
    binary_protocol_send_heartbeat(&protocol_ctx);

    // Send telemetry burst
    binary_protocol_send_telemetry_burst(&protocol_ctx);
    
    Status_Update(20);
}

// ============================================================================
// UART INTERRUPT CALLBACKS
// ============================================================================

/**
 * @brief UART RX Complete callback
 * Called when DMA transfer completes (for circular buffer, this indicates buffer wrap)
 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART1) {
        // USART1 doesn't have DMA, so this won't be called
        // Protocol will use polling mode instead
    }
}

/**
 * @brief UART TX Complete callback
 */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART1) {
        binary_protocol_tx_complete(&protocol_ctx);
    }
}

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
 *     MX_USART2_UART_Init();
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
