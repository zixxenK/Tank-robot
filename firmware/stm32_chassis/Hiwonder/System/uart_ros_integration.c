/**
 * @file uart_ros_integration.c
 * @brief UART callback integration for ROS command handler
 * 
 * Add this file to your STM32 project to integrate ROS command handling
 * with the existing UART infrastructure.
 */

#include "main.h"
#include "usart.h"
#include "uart_ros_cmd.h"

// RX buffer for USART2
static uint8_t usart2_rx_buffer[1];

/**
 * @brief Initialize USART2 for ROS command reception
 * Call this from your main() or initialization code
 */
void uart_ros_integration_init(void) {
    // Start interrupt-based reception on USART2
    HAL_UART_Receive_IT(&huart2, usart2_rx_buffer, 1);
}

/**
 * @brief UART Reception Complete Callback
 * This is called by HAL when a byte is received via USART2
 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART2) {
        // Process received byte through ROS command handler
        uart_ros_process_byte(usart2_rx_buffer[0]);
        
        // Restart reception for next byte
        HAL_UART_Receive_IT(&huart2, usart2_rx_buffer, 1);
    }
}

/**
 * @brief Integration example - add this to your main.c or app.c
 * 
 * In app_task_entry() or main():
 * 
 *   #include "uart_ros_integration.h"
 *   
 *   void app_task_entry(void *argument) {
 *       // ... existing initialization ...
 *       
 *       // Initialize ROS command handler
 *       uart_ros_cmd_init();
 *       
 *       // Initialize UART integration
 *       uart_ros_integration_init();
 *       
 *       // ... rest of your code ...
 *   }
 */
