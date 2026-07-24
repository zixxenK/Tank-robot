/**
  ******************************************************************************
  * @file           : i2c_protocol.h
  * @brief          : I2C protocol definitions for sensor communication
  ******************************************************************************
  * @attention
  *
  * Rock64 Ranger - I2C Sensor Protocol
  * Defines I2C addresses and register maps for MPU6050 IMU and other sensors
  *
  ******************************************************************************
  */

#ifndef __I2C_PROTOCOL_H
#define __I2C_PROTOCOL_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"

/* MPU6050 I2C Address */
#define MPU6050_I2C_ADDR         0xD0  // 0x68 << 1 (8-bit address)
#define MPU6050_I2C_ADDR_READ    0xD1

/* MPU6050 Register Addresses */
#define MPU6050_REG_SMPLRT_DIV    0x19
#define MPU6050_REG_CONFIG       0x1A
#define MPU6050_REG_GYRO_CONFIG   0x1B
#define MPU6050_REG_ACCEL_CONFIG  0x1C
#define MPU6050_REG_FIFO_EN       0x23
#define MPU6050_REG_I2C_MST_CTRL  0x24
#define MPU6050_REG_I2C_SLV0_ADDR 0x25
#define MPU6050_REG_I2C_SLV0_REG  0x26
#define MPU6050_REG_I2C_SLV0_CTRL 0x27
#define MPU6050_REG_I2C_SLV1_ADDR 0x28
#define MPU6050_REG_I2C_SLV1_REG  0x29
#define MPU6050_REG_I2C_SLV1_CTRL 0x2A
#define MPU6050_REG_I2C_SLV2_ADDR 0x2B
#define MPU6050_REG_I2C_SLV2_REG  0x2C
#define MPU6050_REG_I2C_SLV2_CTRL 0x2D
#define MPU6050_REG_I2C_SLV3_ADDR 0x2E
#define MPU6050_REG_I2C_SLV3_REG  0x2F
#define MPU6050_REG_I2C_SLV3_CTRL 0x30
#define MPU6050_REG_I2C_SLV4_ADDR 0x31
#define MPU6050_REG_I2C_SLV4_REG  0x32
#define MPU6050_REG_I2C_SLV4_DO   0x33
#define MPU6050_REG_I2C_SLV4_CTRL 0x34
#define MPU6050_REG_I2C_SLV4_DI   0x35
#define MPU6050_REG_I2C_MST_DELAY 0x36
#define MPU6050_REG_I2C_STATUS    0x3A
#define MPU6050_REG_INT_PIN_CFG   0x37
#define MPU6050_REG_INT_ENABLE    0x38
#define MPU6050_REG_INT_STATUS    0x3A
#define MPU6050_REG_ACCEL_XOUT_H  0x3B
#define MPU6050_REG_ACCEL_XOUT_L  0x3C
#define MPU6050_REG_ACCEL_YOUT_H  0x3D
#define MPU6050_REG_ACCEL_YOUT_L  0x3E
#define MPU6050_REG_ACCEL_ZOUT_H  0x3F
#define MPU6050_REG_ACCEL_ZOUT_L  0x40
#define MPU6050_REG_TEMP_OUT_H    0x41
#define MPU6050_REG_TEMP_OUT_L    0x42
#define MPU6050_REG_GYRO_XOUT_H   0x43
#define MPU6050_REG_GYRO_XOUT_L   0x44
#define MPU6050_REG_GYRO_YOUT_H   0x45
#define MPU6050_REG_GYRO_YOUT_L   0x46
#define MPU6050_REG_GYRO_ZOUT_H   0x47
#define MPU6050_REG_GYRO_ZOUT_L   0x48
#define MPU6050_REG_USER_CTRL     0x6A
#define MPU6050_REG_PWR_MGMT_1    0x6B
#define MPU6050_REG_PWR_MGMT_2    0x6C
#define MPU6050_REG_FIFO_COUNTH   0x72
#define MPU6050_REG_FIFO_COUNTL   0x73
#define MPU6050_REG_FIFO_R_W      0x74
#define MPU6050_REG_WHO_AM_I      0x75

/* MPU6050 Configuration Values */
#define MPU6050_WHO_AM_I_VALUE    0x68
#define MPU6050_ACCEL_RANGE_2G    0x00
#define MPU6050_ACCEL_RANGE_4G    0x08
#define MPU6050_ACCEL_RANGE_8G    0x10
#define MPU6050_ACCEL_RANGE_16G   0x18
#define MPU6050_GYRO_RANGE_250    0x00
#define MPU6050_GYRO_RANGE_500    0x08
#define MPU6050_GYRO_RANGE_1000   0x10
#define MPU6050_GYRO_RANGE_2000   0x18

/* MPU6050 Data Structure */
typedef struct {
  int16_t accel_x;
  int16_t accel_y;
  int16_t accel_z;
  int16_t gyro_x;
  int16_t gyro_y;
  int16_t gyro_z;
  int16_t temperature;
} MPU6050_Data_t;

/* Function Prototypes */
HAL_StatusTypeDef MPU6050_Init(I2C_HandleTypeDef *hi2c);
HAL_StatusTypeDef MPU6050_ReadData(I2C_HandleTypeDef *hi2c, MPU6050_Data_t *data);
HAL_StatusTypeDef MPU6050_WriteRegister(I2C_HandleTypeDef *hi2c, uint8_t reg, uint8_t value);
HAL_StatusTypeDef MPU6050_ReadRegister(I2C_HandleTypeDef *hi2c, uint8_t reg, uint8_t *value);
HAL_StatusTypeDef MPU6050_ReadRegisters(I2C_HandleTypeDef *hi2c, uint8_t reg, uint8_t *buffer, uint16_t length);

#ifdef __cplusplus
}
#endif

#endif /* __I2C_PROTOCOL_H */
