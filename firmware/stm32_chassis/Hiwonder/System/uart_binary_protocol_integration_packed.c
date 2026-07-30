/**
 * @file uart_binary_protocol_integration_packed.c
 * @brief Production integration example for packed binary protocol
 * 
 * This file demonstrates how to integrate the packed binary protocol with:
 * 1. DMA circular buffer for USART3
 * 2. Hardware timer for timeout protection
 * 3. Main loop or FreeRTOS task integration
 * 4. Actual chassis control
 * 
 * HARDWARE CONFIGURATION:
 * - USART3: PD8 (TX), PD9 (RX) for Master communication
 * - DMA1_Stream1: USART3_RX (Circular mode)
 * - DMA1_Stream3: USART3_TX (Normal mode)
 * - TIM2: Hardware watchdog timer (1ms period)
 */

#include "uart_binary_protocol_packed.h"
#include "motor_control.h"
#include "chassis.h"
#include "encoder_motor.h"
#include "adc.h"
#include "imu_mpu6050.h"
#include "imu_integration.h"
#include "battery_integration.h"
#include "status_integration.h"
#include "main.h"
#include "usart.h"
#include "tim.h"
#include <string.h>

// External DMA handles from STM32CubeMX (usart.c)
extern DMA_HandleTypeDef hdma_usart3_rx;
extern DMA_HandleTypeDef hdma_usart3_tx;

// Forward declarations
void binary_protocol_update_and_send_telemetry(void);

// ============================================================================
// PROTOCOL CONTEXT (Global for interrupt access)
// ============================================================================

static BinaryProtocolContext protocol_ctx;

// ============================================================================
// ENCODER STATE
// ============================================================================

static int32_t last_left_encoder = 0;
static int32_t last_right_encoder = 0;

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
    binary_protocol_init_packed(&protocol_ctx,
                               &huart3,           // USART3 for Master TX/RX
                               &hdma_usart3_rx,   // DMA1_Stream1 for RX
                               &hdma_usart3_tx,   // DMA1_Stream3 for TX
                               &htim2,            // TIM2 for watchdog
                               200,               // 200ms command timeout
                               500);              // 500ms heartbeat timeout
    
    // Configure TIM2 for 1ms period (assuming 84MHz APB1 clock)
    // Prescaler: 84MHz / 84 = 1MHz
    // Period: 1MHz / 1000 = 1kHz (1ms)
    htim2.Init.Prescaler = 84 - 1;
    htim2.Init.Period = 1000 - 1;
    HAL_TIM_Base_Init(&htim2);
    
    // Start TIM2
    HAL_TIM_Base_Start(&htim2);
    
    // Initialize encoder reading from motor control layer
    last_left_encoder = MotorControl_GetEncoderCount(0);
    last_right_encoder = MotorControl_GetEncoderCount(1);
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
    if (binary_protocol_check_timeouts(&protocol_ctx)) {
        // Timeout occurred - emergency stop already triggered
        // Additional recovery logic if needed
    }
    
    // Process motor commands
    MotorCommandEntry motor_commands[8];
    uint8_t motor_count = binary_protocol_get_motor_commands(&protocol_ctx,
                                                             motor_commands,
                                                             8);
    
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
    
    // Update and send telemetry
    binary_protocol_update_and_send_telemetry();
}

// ============================================================================
// TELEMETRY UPDATE AND TRANSMISSION
// ============================================================================

void binary_protocol_update_and_send_telemetry(void) {
    // Read encoder values from motor control layer
    int32_t left_encoder = MotorControl_GetEncoderCount(0);   // Motor 0 (left)
    int32_t right_encoder = MotorControl_GetEncoderCount(1);  // Motor 1 (right)
    
    // Read battery voltage from integration layer
    Battery_Update();  // Process ADC DMA buffer
    float battery_voltage = Battery_GetVoltage();
    float battery_current = Battery_GetCurrent();
    
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
    
    // Update status peripherals (10ms period)
    static uint32_t last_status_update = 0;
    uint32_t current_time = HAL_GetTick();
    if (current_time - last_status_update >= 10) {
        Status_Update(10);  // 10ms period
        last_status_update = current_time;
    }
}

// ============================================================================
// UART INTERRUPT CALLBACKS
// ============================================================================

/**
 * @brief UART RX Complete callback
 * Called when DMA transfer completes (for circular buffer, this indicates buffer wrap)
 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART3) {
        // DMA circular buffer handling is automatic
        // The main loop will process the data via binary_protocol_process_dma()
    }
}

/**
 * @brief UART TX Complete callback
 */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART3) {
        protocol_ctx.tx_busy = false;
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
 *     MX_USART3_UART_Init();
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
