/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    microros_transport.c
  * @brief   Custom UART transport for micro-ROS on STM32F407
  ******************************************************************************
  * @attention
  *
  * Custom UART transport implementation for micro-ROS using USART6
  * configured for 115200 baud, 8N1
  *
  ******************************************************************************
  */
/* USER CODE END Header */

#include "microros_transport.h"
#include "usart.h"
#include <string.h>

// UART handle for micro-ROS communication (using USART6)
extern UART_HandleTypeDef huart6;

// Reception buffer
static uint8_t rx_buffer[MICROROS_TRANSPORT_BUFFER_SIZE];
static volatile size_t rx_buffer_head = 0;
static volatile size_t rx_buffer_tail = 0;

// Transmission buffer
static uint8_t tx_buffer[MICROROS_TRANSPORT_BUFFER_SIZE];
static volatile size_t tx_buffer_head = 0;
static volatile size_t tx_buffer_tail = 0;
static volatile bool tx_busy = false;

// Timeout configuration
static uint32_t transport_timeout = 100; // milliseconds

/**
 * @brief Initialize the custom UART transport
 */
void microros_transport_init(void) {
    // Reset buffers
    rx_buffer_head = 0;
    rx_buffer_tail = 0;
    tx_buffer_head = 0;
    tx_buffer_tail = 0;
    tx_busy = false;
    
    // Start UART reception in interrupt mode
    HAL_UART_Receive_IT(&huart6, &rx_buffer[rx_buffer_head], 1);
}

/**
 * @brief Set transport timeout
 * @param timeout Timeout in milliseconds
 */
void microros_transport_set_timeout(uint32_t timeout) {
    transport_timeout = timeout;
}

/**
 * @brief Open the transport (required by micro-ROS)
 * @return 0 on success
 */
int microros_transport_open(struct uxrCustomTransport *transport) {
    (void)transport;
    // Transport is already initialized in microros_transport_init()
    return 0;
}

/**
 * @brief Close the transport (required by micro-ROS)
 * @return 0 on success
 */
int microros_transport_close(struct uxrCustomTransport *transport) {
    (void)transport;
    // Stop UART reception
    HAL_UART_AbortReceive_IT(&huart6);
    return 0;
}

/**
 * @brief Write data to the transport
 * @param transport Transport handle
 * @param buf Buffer to write
 * @param len Length of buffer
 * @param timeout Write timeout
 * @return Number of bytes written, or -1 on error
 */
size_t microros_transport_write(struct uxrCustomTransport *transport,
                                const uint8_t *buf,
                                size_t len,
                                uint8_t *err) {
    (void)transport;
    size_t bytes_written = 0;
    uint32_t start_time = HAL_GetTick();
    
    while (bytes_written < len) {
        // Check if there's space in the TX buffer
        size_t next_head = (tx_buffer_head + 1) % MICROROS_TRANSPORT_BUFFER_SIZE;
        if (next_head != tx_buffer_tail) {
            tx_buffer[tx_buffer_head] = buf[bytes_written];
            tx_buffer_head = next_head;
            bytes_written++;
            
            // Start transmission if not busy
            if (!tx_busy) {
                tx_busy = true;
                HAL_UART_Transmit_IT(&huart6, &tx_buffer[tx_buffer_tail], 1);
            }
        } else {
            // Buffer full, check timeout
            if ((HAL_GetTick() - start_time) > transport_timeout) {
                *err = 1; // Timeout error
                return bytes_written;
            }
            osDelay(1);
        }
    }
    
    *err = 0;
    return bytes_written;
}

/**
 * @brief Read data from the transport
 * @param transport Transport handle
 * @param buf Buffer to read into
 * @param len Length to read
 * @param timeout Read timeout
 * @return Number of bytes read, or -1 on error
 */
size_t microros_transport_read(struct uxrCustomTransport *transport,
                               uint8_t *buf,
                               size_t len,
                               uint8_t *err) {
    (void)transport;
    size_t bytes_read = 0;
    uint32_t start_time = HAL_GetTick();
    
    while (bytes_read < len) {
        // Check if there's data in the RX buffer
        if (rx_buffer_tail != rx_buffer_head) {
            buf[bytes_read] = rx_buffer[rx_buffer_tail];
            rx_buffer_tail = (rx_buffer_tail + 1) % MICROROS_TRANSPORT_BUFFER_SIZE;
            bytes_read++;
        } else {
            // Buffer empty, check timeout
            if ((HAL_GetTick() - start_time) > transport_timeout) {
                *err = 1; // Timeout error
                return bytes_read;
            }
            osDelay(1);
        }
    }
    
    *err = 0;
    return bytes_read;
}

/**
 * @brief UART reception completed callback
 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART6) {
        // Move head pointer
        rx_buffer_head = (rx_buffer_head + 1) % MICROROS_TRANSPORT_BUFFER_SIZE;
        
        // Restart reception for next byte
        HAL_UART_Receive_IT(&huart6, &rx_buffer[rx_buffer_head], 1);
    }
}

/**
 * @brief UART transmission completed callback
 */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART6) {
        // Move tail pointer
        tx_buffer_tail = (tx_buffer_tail + 1) % MICROROS_TRANSPORT_BUFFER_SIZE;
        
        // Check if more data to send
        if (tx_buffer_tail != tx_buffer_head) {
            HAL_UART_Transmit_IT(&huart6, &tx_buffer[tx_buffer_tail], 1);
        } else {
            tx_busy = false;
        }
    }
}

/**
 * @brief Get available bytes in RX buffer
 */
size_t microros_transport_available(void) {
    if (rx_buffer_head >= rx_buffer_tail) {
        return rx_buffer_head - rx_buffer_tail;
    } else {
        return MICROROS_TRANSPORT_BUFFER_SIZE - rx_buffer_tail + rx_buffer_head;
    }
}