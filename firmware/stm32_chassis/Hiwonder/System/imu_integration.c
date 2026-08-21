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
#define IMU_RETRY_PERIOD_MS   1000   // Retry a late/unplugged sensor once/sec

// ============================================================================
// IMU SENSOR INSTANCE
// ============================================================================

static MPU6050ObjectTypeDef imu_sensor;
static bool imu_initialized = false;
static uint32_t last_imu_update_time = 0;
static uint32_t next_imu_init_attempt = 0;
static int imu_last_error = -2;

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
    /* MPU6050 breakout boards select either 0x68 or 0x69 with AD0.  Probe
     * both legal addresses; hard-coding 0x68 made an otherwise healthy IMU
     * silently disappear from ROS when its strap was high. */
    const uint8_t candidate_addresses[] = {
        MPU6050_DEV_ADDR_1,
        MPU6050_DEV_ADDR_2,
    };
    bool device_found = false;
    imu_initialized = false;
    imu_last_error = -2;
    for (size_t i = 0;
         i < (sizeof(candidate_addresses) / sizeof(candidate_addresses[0]));
         ++i) {
        mpu6050_object_init(&imu_sensor, candidate_addresses[i]);

        // Set hardware abstraction functions before probing/configuration.
        imu_sensor.i2c_write_byte_to_mem = i2c_write_byte_to_mem;
        imu_sensor.i2c_read_from_mem = i2c_read_from_mem;
        imu_sensor.sleep_ms = delay_ms;

        if (HAL_I2C_IsDeviceReady(&hi2c2, imu_sensor.dev_addr << 1, 2, 20) ==
            HAL_OK) {
            /* Match the factory Hiwonder driver: an ACK from the onboard
             * MPU-compatible device is authoritative.  Some production
             * controller revisions use a compatible MPU6050 variant whose
            * WHO_AM_I value is not the address byte, so rejecting that value
             * made a working factory sensor disappear as error -2.  The
             * complete 14-byte transfer below remains the real readiness
             * check before telemetry is marked valid. */
            uint8_t who_am_i = 0;
            (void)HAL_I2C_Mem_Read(&hi2c2,
                                   imu_sensor.dev_addr << 1,
                                   MPU6050_WHO_AM_I,
                                   I2C_MEMADD_SIZE_8BIT,
                                   &who_am_i,
                                   1,
                                   20);
            (void)who_am_i;
            device_found = true;
            break;
        }
    }

    /* Probe both addresses first so an absent or unpowered module is a normal
     * telemetry fault instead of a startup failure or an unsafe I2C access. */
    if (!device_found) {
        imu_initialized = false;
        last_imu_update_time = HAL_GetTick();
        next_imu_init_attempt = last_imu_update_time + IMU_RETRY_PERIOD_MS;
        imu_last_error = -2;
        return -2;
    }
    
    // Reset the device. Calibration is intentionally deferred until the
    // sensor path has produced valid samples.
    imu_sensor.base.reset(&imu_sensor.base);

    // Configure for optimal performance
    mpu6050_set_accel_fsr(&imu_sensor, MPU6050_ACCEL_FSR_4G);     // ±4g for good dynamic range
    mpu6050_set_gyro_fsr(&imu_sensor, MPU6050_GYRO_FSR_1000DPS); // ±1000°/s for tank robotics
    mpu6050_set_rate(&imu_sensor, IMU_UPDATE_FREQ_HZ);           // 50Hz sampling rate

    // Set low-pass filter to 20Hz (helps reduce vibration noise)
    mpu6050_set_lpf(&imu_sensor, 20);

    /* Confirm that configuration writes and a complete sensor transfer both
     * work before advertising the IMU as ready. */
    if (mpu6050_set_accel_fsr(&imu_sensor, MPU6050_ACCEL_FSR_4G) != 0 ||
        mpu6050_set_gyro_fsr(&imu_sensor, MPU6050_GYRO_FSR_1000DPS) != 0 ||
        mpu6050_set_rate(&imu_sensor, IMU_UPDATE_FREQ_HZ) != 0 ||
        mpu6050_set_lpf(&imu_sensor, 20) != 0) {
        last_imu_update_time = HAL_GetTick();
        next_imu_init_attempt = last_imu_update_time + IMU_RETRY_PERIOD_MS;
        imu_last_error = -3;
        return -3;
    }

    float startup_accel[3];
    float startup_gyro[3];
    float startup_temperature;
    if (mpu6050_get_all(&imu_sensor,
                        startup_accel,
                        &startup_temperature,
                        startup_gyro) != 0) {
        last_imu_update_time = HAL_GetTick();
        next_imu_init_attempt = last_imu_update_time + IMU_RETRY_PERIOD_MS;
        imu_last_error = -3;
        return -3;
    }

    imu_initialized = true;
    last_imu_update_time = HAL_GetTick();
    next_imu_init_attempt = last_imu_update_time + IMU_RETRY_PERIOD_MS;
    imu_last_error = 0;

    return 0; // Success
}

// ============================================================================
// IMU UPDATE WITH FIXED DELTA TIME
// ============================================================================

int IMU_Update(float *accel, float *gyro) {
    if (!imu_initialized) {
        uint32_t now = HAL_GetTick();
        if ((int32_t)(now - next_imu_init_attempt) >= 0) {
            /* The IMU can be powered after the controller boots. Retry
             * without blocking the motor link or requiring a reset. */
            (void)IMU_Init();
        }
        return imu_last_error; // Not initialized / retry pending
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
        /* Recover from a transient I2C fault instead of publishing stale
         * values forever. The next bounded retry re-probes both addresses. */
        imu_initialized = false;
        imu_last_error = -3;
        next_imu_init_attempt = current_time + IMU_RETRY_PERIOD_MS;
        return -3; // Sensor read failed
    }
    
    /* mpu6050_object_init exposes update(), but the legacy base object does
     * not install get_accel()/get_gyro() callbacks.  Read the values that
     * export_mpu6050_update() populated directly. */
    raw_accel[0] = imu_sensor.accel[0];
    raw_accel[1] = imu_sensor.accel[1];
    raw_accel[2] = imu_sensor.accel[2];
    raw_gyro[0] = imu_sensor.gyro[0];
    raw_gyro[1] = imu_sensor.gyro[1];
    raw_gyro[2] = imu_sensor.gyro[2];
    
    // Apply to output arrays
    /* The MPU6050 driver returns g and degrees/second; ROS Imu requires SI
     * units (m/s^2 and radians/second). */
    const float gravity = 9.80665f;
    const float degrees_to_radians = 0.017453292519943f;
    accel[0] = raw_accel[0] * gravity;
    accel[1] = raw_accel[1] * gravity;
    accel[2] = raw_accel[2] * gravity;

    gyro[0] = raw_gyro[0] * degrees_to_radians;
    gyro[1] = raw_gyro[1] * degrees_to_radians;
    gyro[2] = raw_gyro[2] * degrees_to_radians;
    imu_last_error = 0;
    
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
