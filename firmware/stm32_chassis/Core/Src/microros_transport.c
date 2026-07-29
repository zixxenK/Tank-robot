#include "microros_transport.h"
#include "usart.h"
#include <string.h>

// UART handle for micro-ROS communication (using USART3)
extern UART_HandleTypeDef huart3;

bool microros_transport_open(struct uxrCustomTransport * transport) {
    // UART is already initialized in main.c
    return true;
}

bool microros_transport_close(struct uxrCustomTransport * transport) {
    // UART stays open
    return true;
}

size_t microros_transport_write(struct uxrCustomTransport* transport, const uint8_t* buf, size_t len, uint8_t* err) {
    HAL_UART_Transmit(&huart3, (uint8_t*)buf, len, HAL_MAX_DELAY);
    return len;
}

size_t microros_transport_read(struct uxrCustomTransport* transport, uint8_t* buf, size_t len, int timeout, uint8_t* err) {
    HAL_UART_Receive(&huart3, buf, len, timeout);
    return len;
}