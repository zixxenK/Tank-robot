/**
  ******************************************************************************
  * @file           : mpu6050.c
  * @brief          : MPU6050 IMU driver implementation
  ******************************************************************************
  * @attention
  *
  * Rock64 Ranger - MPU6050 Driver
  *
  ******************************************************************************
  */

#include "i2c_protocol.h"
#include <string.h>

/**
  * @brief  Initialize MPU6050 sensor
  * @param  hi2c: I2C handle
  * @retval HAL status
  */
HAL_StatusTypeDef MPU6050_Init(I2C_HandleTypeDef *hi2c)
{
  HAL_StatusTypeDef status;
  uint8_t who_am_i;

  /* Check device ID */
  status = MPU6050_ReadRegister(hi2c, MPU6050_REG_WHO_AM_I, &who_am_i);
  if (status != HAL_OK || who_am_i != MPU6050_WHO_AM_I_VALUE)
  {
    return HAL_ERROR;
  }

  /* Wake up MPU6050 */
  status = MPU6050_WriteRegister(hi2c, MPU6050_REG_PWR_MGMT_1, 0x00);
  if (status != HAL_OK)
  {
    return status;
  }

  /* Configure sample rate: 1kHz / (1 + SMPLRT_DIV) */
  status = MPU6050_WriteRegister(hi2c, MPU6050_REG_SMPLRT_DIV, 0x07); // ~125Hz
  if (status != HAL_OK)
  {
    return status;
  }

  /* Configure digital low-pass filter */
  status = MPU6050_WriteRegister(hi2c, MPU6050_REG_CONFIG, 0x03);
  if (status != HAL_OK)
  {
    return status;
  }

  /* Configure gyroscope: +/- 500 deg/s */
  status = MPU6050_WriteRegister(hi2c, MPU6050_REG_GYRO_CONFIG, MPU6050_GYRO_RANGE_500);
  if (status != HAL_OK)
  {
    return status;
  }

  /* Configure accelerometer: +/- 4g */
  status = MPU6050_WriteRegister(hi2c, MPU6050_REG_ACCEL_CONFIG, MPU6050_ACCEL_RANGE_4G);
  if (status != HAL_OK)
  {
    return status;
  }

  return HAL_OK;
}

/**
  * @brief  Read all sensor data from MPU6050
  * @param  hi2c: I2C handle
  * @param  data: Pointer to data structure
  * @retval HAL status
  */
HAL_StatusTypeDef MPU6050_ReadData(I2C_HandleTypeDef *hi2c, MPU6050_Data_t *data)
{
  HAL_StatusTypeDef status;
  uint8_t buffer[14];

  /* Read 14 bytes starting from ACCEL_XOUT_H */
  status = MPU6050_ReadRegisters(hi2c, MPU6050_REG_ACCEL_XOUT_H, buffer, 14);
  if (status != HAL_OK)
  {
    return status;
  }

  /* Parse accelerometer data */
  data->accel_x = (int16_t)((buffer[0] << 8) | buffer[1]);
  data->accel_y = (int16_t)((buffer[2] << 8) | buffer[3]);
  data->accel_z = (int16_t)((buffer[4] << 8) | buffer[5]);

  /* Parse temperature data */
  data->temperature = (int16_t)((buffer[6] << 8) | buffer[7]);

  /* Parse gyroscope data */
  data->gyro_x = (int16_t)((buffer[8] << 8) | buffer[9]);
  data->gyro_y = (int16_t)((buffer[10] << 8) | buffer[11]);
  data->gyro_z = (int16_t)((buffer[12] << 8) | buffer[13]);

  return HAL_OK;
}

/**
  * @brief  Write a single register to MPU6050
  * @param  hi2c: I2C handle
  * @param  reg: Register address
  * @param  value: Value to write
  * @retval HAL status
  */
HAL_StatusTypeDef MPU6050_WriteRegister(I2C_HandleTypeDef *hi2c, uint8_t reg, uint8_t value)
{
  uint8_t buffer[2];
  buffer[0] = reg;
  buffer[1] = value;

  return HAL_I2C_Master_Transmit(hi2c, MPU6050_I2C_ADDR, buffer, 2, 100);
}

/**
  * @brief  Read a single register from MPU6050
  * @param  hi2c: I2C handle
  * @param  reg: Register address
  * @param  value: Pointer to store read value
  * @retval HAL status
  */
HAL_StatusTypeDef MPU6050_ReadRegister(I2C_HandleTypeDef *hi2c, uint8_t reg, uint8_t *value)
{
  return MPU6050_ReadRegisters(hi2c, reg, value, 1);
}

/**
  * @brief  Read multiple registers from MPU6050
  * @param  hi2c: I2C handle
  * @param  reg: Starting register address
  * @param  buffer: Buffer to store read data
  * @param  length: Number of bytes to read
  * @retval HAL status
  */
HAL_StatusTypeDef MPU6050_ReadRegisters(I2C_HandleTypeDef *hi2c, uint8_t reg, uint8_t *buffer, uint16_t length)
{
  HAL_StatusTypeDef status;

  /* Send register address */
  status = HAL_I2C_Master_Transmit(hi2c, MPU6050_I2C_ADDR, &reg, 1, 100);
  if (status != HAL_OK)
  {
    return status;
  }

  /* Read data */
  status = HAL_I2C_Master_Receive(hi2c, MPU6050_I2C_ADDR_READ, buffer, length, 100);
  return status;
}
