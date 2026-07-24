//
// Created by lucas on 2022-08-29.
//

#include <stdio.h>
#include "serial_servo.h"
#include "global.h"
#include "usart.h"
#include <stdarg.h>
#include <string.h>

#define GET_LOW_BYTE(A) ((uint8_t)(A))
//宏函数 获得A的低八位
#define GET_HIGH_BYTE(A) ((uint8_t)((A) >> 8))
//宏函数 获得A的高八位
#define BYTE_TO_HW(A, B) ((((uint16_t)(A)) << 8) | (uint8_t)(B))
//宏函数 将高地八位合成为十六位

uint8_t uart2_rx_buffer[256];
uint8_t uart2_tx_buffer[256];
uint32_t response_timeout = 0u;

static inline void SerialWrite(const uint8_t *buffer, uint16_t length) {
    HAL_GPIO_WritePin(SERIAL_SERVO_RX_EN_GPIO_Port, SERIAL_SERVO_RX_EN_Pin, GPIO_PIN_SET);
    HAL_GPIO_WritePin(SERIAL_SERVO_TX_EN_GPIO_Port, SERIAL_SERVO_TX_EN_Pin, GPIO_PIN_RESET);
    HAL_UART_Transmit(&huart6, (void *) buffer, length, 1000);
    HAL_GPIO_WritePin(SERIAL_SERVO_RX_EN_GPIO_Port, SERIAL_SERVO_RX_EN_Pin, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(SERIAL_SERVO_TX_EN_GPIO_Port, SERIAL_SERVO_TX_EN_Pin, GPIO_PIN_SET);
}

static inline void SerialRead(const uint8_t *buffer, uint16_t length) {
    HAL_GPIO_WritePin(SERIAL_SERVO_RX_EN_GPIO_Port, SERIAL_SERVO_RX_EN_Pin, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(SERIAL_SERVO_TX_EN_GPIO_Port, SERIAL_SERVO_TX_EN_Pin, GPIO_PIN_SET);
    HAL_UART_Receive_IT(&huart1, (void *) buffer, length);
    HAL_UART_Transmit(&huart6, (void *) buffer, length, 1000);
}

static inline uint8_t CheckSum(const uint8_t buf[]) {
    uint16_t temp = 0;
    for (int i = 2; i < buf[3] + 2; ++i) {
        temp += buf[i];
    }
    temp = ~temp;
    return (uint8_t) temp;
}

void serial_servo_set_id(uint8_t old_id, uint8_t new_id) {
    uint8_t buf[7];
    buf[0] = buf[1] = SERIAL_SERVO_FRAME_HEADER;
    buf[2] = old_id;
    buf[3] = 4;
    buf[4] = SERIAL_SERVO_ID_WRITE;
    buf[5] = new_id;
    buf[6] = CheckSum(buf);
    SerialWrite(buf, 7);
}

void serial_servo_set_position(uint8_t servo_id, uint16_t position, uint16_t duration) {
    if (servo_id > 31) {  //舵机ID不能大于31,可根据对应控制板修改
        return;
    }
    uint8_t buffer[10];
    position = position > 1000 ? 1000 : position;
    buffer[0] = SERIAL_SERVO_FRAME_HEADER;
    buffer[1] = SERIAL_SERVO_FRAME_HEADER;
    buffer[2] = servo_id;
    buffer[3] = 7;
    buffer[4] = SERIAL_SERVO_MOVE_TIME_WRITE;
    buffer[5] = GET_LOW_BYTE(position);
    buffer[6] = GET_HIGH_BYTE(position);
    buffer[7] = GET_LOW_BYTE(duration);
    buffer[8] = GET_HIGH_BYTE(duration);
    buffer[9] = CheckSum(buffer);
    SerialWrite(buffer, 10);
}

void serial_servo_stop(uint8_t servo_id) {
    uint8_t buffer[10];
    buffer[0] = SERIAL_SERVO_FRAME_HEADER;
    buffer[1] = SERIAL_SERVO_FRAME_HEADER;
    buffer[2] = servo_id;
    buffer[3] = 6;
    buffer[4] = SERIAL_SERVO_MOVE_STOP;
    buffer[5] = CheckSum(buffer);
    SerialWrite(buffer, 6);
}

void serial_servo_set_deviation(uint8_t servo_id, int new_deviation) {
    uint8_t buffer[10];
    buffer[0] = SERIAL_SERVO_FRAME_HEADER;
    buffer[1] = SERIAL_SERVO_FRAME_HEADER;
    buffer[2] = servo_id;
    buffer[3] = 7;
    buffer[4] = SERIAL_SERVO_ANGLE_OFFSET_ADJUST;
    buffer[5] = (uint8_t) ((int8_t) new_deviation);
    buffer[6] = CheckSum(buffer);
    SerialWrite(buffer, 7);
}

void serial_servo_read_deviation(uint8_t servo_id) {
    uint8_t buffer[10];
    buffer[0] = SERIAL_SERVO_FRAME_HEADER;
    buffer[1] = SERIAL_SERVO_FRAME_HEADER;
    buffer[2] = servo_id;
    buffer[3] = 6;
    buffer[4] = SERIAL_SERVO_ANGLE_OFFSET_READ;
    buffer[5] = CheckSum(buffer);
    SerialWrite(buffer, 6);
}

void serial_servo_save_deviation(uint8_t servo_id) {
    uint8_t buffer[10];
    buffer[0] = SERIAL_SERVO_FRAME_HEADER;
    buffer[1] = SERIAL_SERVO_FRAME_HEADER;
    buffer[2] = servo_id;
    buffer[3] = 6;
    buffer[4] = SERIAL_SERVO_ANGLE_OFFSET_WRITE;
    buffer[5] = CheckSum(buffer);
    SerialWrite(buffer, 6);
}

void serial_servo_unload(uint8_t servo_id) {
    uint8_t buffer[7];
    buffer[0] = SERIAL_SERVO_FRAME_HEADER;
    buffer[1] = SERIAL_SERVO_FRAME_HEADER;
    buffer[2] = servo_id;
    buffer[3] = 7;
    buffer[4] = SERIAL_SERVO_LOAD_OR_UNLOAD_WRITE;
    buffer[5] = 0;
    buffer[6] = CheckSum(buffer);
    SerialWrite(buffer, 7);
}

int serial_servo_read_position(uint8_t servo_id) {
    int ret = 0;
    uint8_t buffer[6];
    if (response_timeout!=0) { /* 当前有命令等待返回不能发送 */
        return -1;
    }

    buffer[0] = SERIAL_SERVO_FRAME_HEADER;
    buffer[1] = SERIAL_SERVO_FRAME_HEADER;
    buffer[2] = servo_id;
    buffer[3] = 6;
    buffer[4] = SERIAL_SERVO_POS_READ;
    buffer[5] = CheckSum(buffer);
    SerialWrite(buffer, 6);
    return ret;
}

enum SERIAL_SERVO_RECV_STATE {
    SERIAL_SERVO_WAIT_FOR_START_1,
    SERIAL_SERVO_RECV_START_2,
    SERIAL_SERVO_RECV_SERVO_ID,
    SERIAL_SERVO_RECV_LENGTH,
    SERIAL_SERVO_RECV_COMMAND,
    SERIAL_SERVO_RECV_ARGUMENTS,
    SERIAL_SERVO_RECV_CHECKSUM,
};

static uint8_t rx_buffer[128];
struct __attribute__((packed)) servo_frame {
    uint8_t servo_id;
    uint8_t length;
    uint8_t command;
    uint8_t data[];
};
static uint8_t args = 0;
static struct servo_frame *rx_frame = (void *) rx_buffer;

void serial_servo_received_handler(uint8_t rx_byte) {
    static enum SERIAL_SERVO_RECV_STATE state = SERIAL_SERVO_WAIT_FOR_START_1;
    switch (state) {
        case SERIAL_SERVO_WAIT_FOR_START_1: {
            state = 0x55==rx_byte ? SERIAL_SERVO_RECV_START_2 : SERIAL_SERVO_WAIT_FOR_START_1;
            break;
        }
        case SERIAL_SERVO_RECV_START_2: {
            state = 0x55==rx_byte ? SERIAL_SERVO_RECV_SERVO_ID : SERIAL_SERVO_WAIT_FOR_START_1;
            break;
        }
        case SERIAL_SERVO_RECV_SERVO_ID: {
            rx_frame->servo_id = rx_byte;
            state = SERIAL_SERVO_RECV_LENGTH;
            break;
        }
        case SERIAL_SERVO_RECV_LENGTH: {
            rx_frame->length = rx_byte;
            state = SERIAL_SERVO_RECV_COMMAND;
            break;
        }
        case SERIAL_SERVO_RECV_COMMAND: {
            rx_frame->command = rx_byte;
            args = 0;
            state = rx_frame->length==6 ? SERIAL_SERVO_RECV_CHECKSUM : SERIAL_SERVO_RECV_ARGUMENTS;
            break;
        }
        case SERIAL_SERVO_RECV_ARGUMENTS: {
            rx_frame->data[args++] = rx_byte;
            if (args + 5==rx_frame->length) {
                state = SERIAL_SERVO_RECV_CHECKSUM;
            }
            break;
        }
        case SERIAL_SERVO_RECV_CHECKSUM: {
            state = SERIAL_SERVO_WAIT_FOR_START_1;
            break;
        }

        default: {
            state = SERIAL_SERVO_WAIT_FOR_START_1;
            break;
        }
    }
}

