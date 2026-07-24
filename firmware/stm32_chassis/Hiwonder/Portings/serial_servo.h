//
// Created by lucas on 2022-08-29.
//
#ifndef __SERIAL_SERVO_H
#define __SERIAL_SERVO_H

#include <stdint.h>

#define SERIAL_SERVO_FRAME_HEADER         0x55
#define SERIAL_SERVO_MOVE_TIME_WRITE      1
#define SERIAL_SERVO_MOVE_TIME_READ       2
#define SERIAL_SERVO_MOVE_TIME_WAIT_WRITE 7
#define SERIAL_SERVO_MOVE_TIME_WAIT_READ  8
#define SERIAL_SERVO_MOVE_START           11
#define SERIAL_SERVO_MOVE_STOP            12
#define SERIAL_SERVO_ID_WRITE             13
#define SERIAL_SERVO_ID_READ              14
#define SERIAL_SERVO_ANGLE_OFFSET_ADJUST  17
#define SERIAL_SERVO_ANGLE_OFFSET_WRITE   18
#define SERIAL_SERVO_ANGLE_OFFSET_READ    19
#define SERIAL_SERVO_ANGLE_LIMIT_WRITE    20
#define SERIAL_SERVO_ANGLE_LIMIT_READ     21
#define SERIAL_SERVO_VIN_LIMIT_WRITE      22
#define SERIAL_SERVO_VIN_LIMIT_READ       23
#define SERIAL_SERVO_TEMP_MAX_LIMIT_WRITE 24
#define SERIAL_SERVO_TEMP_MAX_LIMIT_READ  25
#define SERIAL_SERVO_TEMP_READ            26
#define SERIAL_SERVO_VIN_READ             27
#define SERIAL_SERVO_POS_READ             28
#define SERIAL_SERVO_OR_MOTOR_MODE_WRITE  29
#define SERIAL_SERVO_OR_MOTOR_MODE_READ   30
#define SERIAL_SERVO_LOAD_OR_UNLOAD_WRITE 31
#define SERIAL_SERVO_LOAD_OR_UNLOAD_READ  32
#define SERIAL_SERVO_LED_CTRL_WRITE       33
#define SERIAL_SERVO_LED_CTRL_READ        34
#define SERIAL_SERVO_LED_ERROR_WRITE      35
#define SERIAL_SERVO_LED_ERROR_READ       36

#define CMD_SERVO_MOVE 0x03

#define SERIAL_DEBUG 1

void serial_servo_set_position(uint8_t servo_id, uint16_t position, uint16_t duration);
void moveServo(uint8_t servoID, uint16_t Position, uint16_t Time);
void LobotSerialServoSetID(uint8_t oldID, uint8_t newID);
void LobotSerialServoMove(uint8_t id, int16_t position, uint16_t time);
void LobotSerialServoUnload(uint8_t id);
void LobotSerialServoLoad(uint8_t id);
int LobotSerialServoReadPosition(uint8_t id);
int LobotSerialMsgHandle(void);
void moveServos(uint8_t Num, uint16_t Time, ...);
#endif
