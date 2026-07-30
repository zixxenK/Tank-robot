/**
 * @file uart_binary_protocol_integration.c
 * @brief Integration example for binary protocol with STM32 firmware
 * 
 * This file shows how to integrate the binary protocol handler with the
 * existing Hiwonder STM32 firmware for the tank robot chassis control.
 */

#include "uart_binary_protocol.h"
#include "chassis.h"
#include "main.h"
#include "usart.h"
#include "encoder_motor.h"
#include "adc.h"
#include "imu_mpu6050.h"

// External chassis object from Hiwonder system
extern ChassisTypeDef *chassis;

// Protocol context
static BinaryProtocolContext protocol_ctx;

// Encoder state
static int32_t last_left_encoder = 0;
static int32_t last_right_encoder = 0;

// Battery state
static float battery_voltage = 0.0f;
static float battery_current = 0.0f;

// IMU state
static float imu_accel[3] = {0.0f, 0.0f, 0.0f};
static float imu_gyro[3] = {0.0f, 0.0f, 0.0f};

/**
 * @brief Initialize binary protocol integration
 * Call this from your main() or initialization function
 */
void binary_protocol_integration_init(void) {
    // Initialize protocol handler with USART3 (Master TX/RX on PD8/PD9)
    // Using DMA1_Stream1 for RX and DMA1_Stream3 for TX
    binary_protocol_init(&protocol_ctx, 
                        &huart3,          // USART3 handle
                        &hdma_usart3_rx,  // RX DMA handle
                        &hdma_usart3_tx,  // TX DMA handle
                        200);             // 200ms command timeout
    
    // Enable telemetry
    binary_protocol_set_encoder_telemetry(&protocol_ctx, true);
    binary_protocol_set_battery_telemetry(&protocol_ctx, true);
    binary_protocol_set_imu_telemetry(&protocol_ctx, true);
    
    // Set telemetry interval (100ms = 10Hz)
    binary_protocol_set_telemetry_interval(&protocol_ctx, 100);
}

/**
 * @brief UART RX Complete callback
 * Call this from HAL_UART_RxCpltCallback in stm32f4xx_it.c
 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART3) {
        // Calculate received bytes using DMA
        uint16_t rx_pos = RX_BUFFER_SIZE - __HAL_DMA_GET_COUNTER(&hdma_usart3_rx);
        
        // Process received data
        if (rx_pos > 0) {
            binary_protocol_process_buffer(&protocol_ctx, 
                                           protocol_ctx.rx_buffer, 
                                           rx_pos);
        }
        
        // Restart DMA reception
        HAL_UART_Receive_DMA(&huart3, protocol_ctx.rx_buffer, RX_BUFFER_SIZE);
    }
}

/**
 * @brief Periodic task for protocol integration
 * Call this from your main loop or a FreeRTOS task
 */
void binary_protocol_integration_periodic_task(void) {
    // Call protocol periodic task
    binary_protocol_periodic_task(&protocol_ctx);
    
    // Process motor commands
    MotorCommand motor_commands[8];
    uint8_t motor_count = binary_protocol_get_motor_commands(&protocol_ctx, 
                                                             motor_commands, 
                                                             8);
    
    if (motor_count > 0) {
        // Apply motor commands to chassis
        for (uint8_t i = 0; i < motor_count; i++) {
            uint8_t motor_id = motor_commands[i].motor_id;
            float rps = motor_commands[i].rps;
            
            // Convert normalized RPS to chassis velocity
            // Assuming max speed of 500 mm/s
            float motor_speed = rps * 500.0f;
            
            // Apply to chassis based on motor ID
            if (motor_id == 0) {
                // Left motor - affects linear and angular velocity
                chassis->set_velocity(chassis, motor_speed, 0.0f, 0.0f);
            } else if (motor_id == 1) {
                // Right motor - affects linear and angular velocity
                chassis->set_velocity(chassis, 0.0f, motor_speed, 0.0f);
            }
        }
    }
    
    // Update and send encoder telemetry
    update_encoder_telemetry();
    
    // Update and send battery telemetry
    update_battery_telemetry();
    
    // Update and send IMU telemetry
    update_imu_telemetry();
}

/**
 * @brief Update encoder telemetry
 */
void update_encoder_telemetry(void) {
    // Read encoder values from your encoder system
    // This is pseudo-code - adapt to your actual encoder interface
    int32_t left_encoder = 0;
    int32_t right_encoder = 0;
    
    // Example: if using encoder_motor interface
    // left_encoder = encoder_motor_get_count(&left_motor);
    // right_encoder = encoder_motor_get_count(&right_motor);
    
    // Send if values changed
    if (left_encoder != last_left_encoder || right_encoder != last_right_encoder) {
        binary_protocol_send_encoder_telemetry(&protocol_ctx, left_encoder, right_encoder);
        last_left_encoder = left_encoder;
        last_right_encoder = right_encoder;
    }
}

/**
 * @brief Update battery telemetry
 */
void update_battery_telemetry(void) {
    // Read battery voltage from ADC
    // Assuming ADC channel 8 for battery voltage
    uint16_t adc_value = 0;
    
    // Example: if using ADC interface
    // HAL_ADC_Start(&hadc1);
    // HAL_ADC_PollForConversion(&hadc1, 100);
    // adc_value = HAL_ADC_GetValue(&hadc1);
    
    // Convert ADC value to voltage (assuming 12-bit ADC, voltage divider)
    // float voltage = (adc_value / 4095.0f) * 3.3f * VOLTAGE_DIVIDER_RATIO;
    float voltage = 12.0f; // Placeholder
    
    // Calculate current (if you have current sensing)
    float current = 0.0f; // Placeholder
    
    // Update if voltage changed significantly
    if (fabs(voltage - battery_voltage) > 0.1f) {
        battery_voltage = voltage;
        battery_current = current;
        binary_protocol_send_battery_telemetry(&protocol_ctx, voltage, current);
    }
}

/**
 * @brief Update IMU telemetry
 */
void update_imu_telemetry(void) {
    // Read IMU data from MPU6050 or similar
    // This is pseudo-code - adapt to your actual IMU interface
    
    // Example: if using imu_mpu6050 interface
    // imu_mpu6050_get_accel(&imu_accel[0], &imu_accel[1], &imu_accel[2]);
    // imu_mpu6050_get_gyro(&imu_gyro[0], &imu_gyro[1], &imu_gyro[2]);
    
    // Send IMU data at configured interval
    static uint32_t last_imu_time = 0;
    uint32_t now = HAL_GetTick();
    
    if (now - last_imu_time >= protocol_ctx.telemetry_interval_ms) {
        last_imu_time = now;
        binary_protocol_send_imu_telemetry(&protocol_ctx,
                                           imu_accel[0], imu_accel[1], imu_accel[2],
                                           imu_gyro[0], imu_gyro[1], imu_gyro[2]);
    }
}

/**
 * @brief Get protocol statistics for diagnostics
 */
const ProtocolStats* binary_protocol_integration_get_stats(void) {
    return binary_protocol_get_stats(&protocol_ctx);
}

/**
 * @brief Emergency stop - called from safety systems
 */
void binary_protocol_integration_emergency_stop(void) {
    // Clear all motor commands
    MotorCommand motor_commands[8];
    uint8_t motor_count = binary_protocol_get_motor_commands(&protocol_ctx, 
                                                             motor_commands, 
                                                             8);
    
    // Stop chassis
    if (chassis) {
        chassis->stop(chassis);
    }
    
    // Send error indication
    binary_protocol_send_error(&protocol_ctx, 0x01); // Error code 0x01 = emergency stop
}

/**
 * @brief Example FreeRTOS task for protocol handling
 * Create this task in your FreeRTOS initialization if using RTOS
 */
void binary_protocol_task(void *argument) {
    (void)argument;
    
    binary_protocol_integration_init();
    
    for (;;) {
        binary_protocol_integration_periodic_task();
        
        // 10ms loop period = 100Hz
        osDelay(10);
    }
}
