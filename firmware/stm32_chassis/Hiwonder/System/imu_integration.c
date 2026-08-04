/**
 * @file imu_integration.c
 * @brief IMU integration wrapper with fixed delta time for Madgwick filter
 * 
 * CRITICAL IMPLEMENTATION NOTES:
 * 1. Fixed delta time (dt) = 0.02f (50Hz) - prevents integration drift from loop jitter
 * 2. I2C reads in 50Hz telemetry burst - NOT in 100Hz motor control loop
 * 3. Uses Hiwonder's existing MPU6050 driver with Fusion library
 */

#include "imu_integration.h"
#include "imu_mpu6050.h"
#include "i2c.h"
#include "main.h"

// ============================================================================
// FIXED DELTA TIME CONFIGURATION
// ============================================================================

#define IMU_UPDATE_FREQ_HZ     50     // 50Hz update rate
#define IMU_FIXED_DT_SEC       0.02f  // Fixed delta time (1/50 = 0.02s)
#define IMU_UPDATE_PERIOD_MS  20     // 20ms period

// ============================================================================
// IMU SENSOR INSTANCE
// ============================================================================

static MPU6050ObjectTypeDef imu_sensor;
static bool imu_initialized = false;
static uint32_t last_imu_update_time = 0;

// ============================================================================
// I2C HARDWARE ABSTRACTION
// ============================================================================

static int i2c_write_byte_to_mem(MPU6050ObjectTypeDef *self, uint8_t reg_addr, uint8_t data) {
    return HAL_I2C_Mem_Write(&hi2c2, self->dev_addr << 1, reg_addr, I2C_MEMADD_SIZE_8BIT, &data, 1, 100);
}

static int i2c_read_from_mem(MPU6050ObjectTypeDef *self, uint8_t reg_addr, uint32_t length, uint8_t *buf) {
    return HAL_I2C_Mem_Read(&hi2c2, self->dev_addr << 1, reg_addr, I2C_MEMADD_SIZE_8BIT, buf, length, 100);
}

static void delay_ms(uint32_t ms) {
    HAL_Delay(ms);
}

// ============================================================================
// IMU INITIALIZATION
// ============================================================================

int IMU_Init(void) {
    // Initialize MPU6050 object
    mpu6050_object_init(&imu_sensor, MPU6050_DEV_ADDR_1);
    
    // Set hardware abstraction functions
    imu_sensor.i2c_write_byte_to_mem = i2c_write_byte_to_mem;
    imu_sensor.i2c_read_from_mem = i2c_read_from_mem;
    imu_sensor.sleep_ms = delay_ms;

    // Temporary safety bypass: IMU bring-up currently hardfaults on this
    // hardware/firmware path. Keep IMU disabled so drivetrain protocol can boot.
    imu_initialized = false;
    last_imu_update_time = HAL_GetTick();
    return -1;
    
    // Reset and calibrate IMU
    imu_sensor.base.reset(&imu_sensor.base);
    imu_sensor.base.calibrat(&imu_sensor.base);

    // Configure for optimal performance
    mpu6050_set_accel_fsr(&imu_sensor, MPU6050_ACCEL_FSR_4G);     // ±4g for good dynamic range
    mpu6050_set_gyro_fsr(&imu_sensor, MPU6050_GYRO_FSR_1000DPS); // ±1000°/s for tank robotics
    mpu6050_set_rate(&imu_sensor, IMU_UPDATE_FREQ_HZ);           // 50Hz sampling rate

    // Set low-pass filter to 20Hz (helps reduce vibration noise)
    mpu6050_set_lpf(&imu_sensor, 20);

    imu_initialized = true;
    last_imu_update_time = HAL_GetTick();

    return 0; // Success
}

// ============================================================================
// IMU UPDATE WITH FIXED DELTA TIME
// ============================================================================

int IMU_Update(float *accel, float *gyro) {
    if (!imu_initialized) {
        return -1; // Not initialized
    }
    
    uint32_t current_time = HAL_GetTick();
    
    // Rate limiting: Only update at 50Hz (20ms period)
    // This prevents I2C blocking in the 100Hz motor control loop
    if ((current_time - last_imu_update_time) < IMU_UPDATE_PERIOD_MS) {
        return -2; // Not time yet
    }
    
    last_imu_update_time = current_time;
    
    // Read raw sensor data
    float raw_accel[3], raw_gyro[3];
    if (imu_sensor.base.update(&imu_sensor.base) != 0) {
        return -3; // Sensor read failed
    }
    
    // Get calibrated data
    imu_sensor.base.get_accel(&imu_sensor.base, raw_accel);
    imu_sensor.base.get_gyro(&imu_sensor.base, raw_gyro);
    
    // Apply to output arrays
    accel[0] = raw_accel[0];
    accel[1] = raw_accel[1];
    accel[2] = raw_accel[2];
    
    gyro[0] = raw_gyro[0];
    gyro[1] = raw_gyro[1];
    gyro[2] = raw_gyro[2];
    
    return 0; // Success
}

// ============================================================================
// IMU ORIENTATION DATA (Euler Angles & Quaternions)
// ============================================================================

int IMU_GetOrientation(float *rpy, float *quat) {
    if (!imu_initialized) {
        return -1;
    }
    
    // Get Euler angles (roll, pitch, yaw)
    if (imu_sensor.base.get_euler(&imu_sensor.base, rpy) != 0) {
        return -2;
    }
    
    // Get quaternion (w, x, y, z)
    if (imu_sensor.base.get_quat(&imu_sensor.base, quat) != 0) {
        return -3;
    }
    
    return 0;
}

// ============================================================================
// IMU STATUS CHECKS
// ============================================================================

bool IMU_IsReady(void) {
    return imu_initialized;
}

int IMU_GetTemperature(float *temp) {
    if (!imu_initialized) {
        return -1;
    }
    
    return mpu6050_get_temperature(&imu_sensor, temp);
}