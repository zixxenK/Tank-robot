/**
 * @file imu_integration.c
 * @brief IMU integration wrapper with fixed delta time for Madgwick filter
 * 
 * CRITICAL IMPLEMENTATION NOTES:
 * 1. Fixed delta time (dt) = 0.02f (50Hz) - prevents integration drift from loop jitter
 * 2. I2C reads in 50Hz telemetry burst - NOT in 100Hz motor control loop
 * 3. Uses Hiwonder's V1.2 onboard QMI8658 driver path.
 */

#include "imu_integration.h"
#include "i2c.h"
#include "main.h"
#include <math.h>
#include <stddef.h>

// ============================================================================
// FIXED DELTA TIME CONFIGURATION
// ============================================================================

#define IMU_UPDATE_PERIOD_MS  20     // 20ms period
#define IMU_RETRY_PERIOD_MS   1000   // Retry a late/unplugged sensor once/sec

// ============================================================================
// QMI8658 V1.2 SENSOR
// ============================================================================

static bool imu_initialized = false;
static uint32_t last_imu_update_time = 0;
static uint32_t next_imu_init_attempt = 0;
static int imu_last_error = -2;
static uint8_t imu_status = IMU_STATUS_UNAVAILABLE;
static uint8_t imu_device_address = 0;
static uint8_t imu_who_am_i = 0;
static uint32_t imu_sample_count = 0;
static uint32_t imu_error_count = 0;

/* Hiwonder's official V1.2 source identifies the onboard device as QMI8658.
 * It is not MPU6050-compatible: the identity and data register maps differ. */
#define QMI8658_ADDR_LOW          0x6AU
#define QMI8658_ADDR_HIGH         0x6BU
#define QMI8658_WHO_AM_I_REG      0x00U
#define QMI8658_WHO_AM_I_VALUE    0x05U
#define QMI8658_CTRL1             0x02U
#define QMI8658_CTRL2             0x03U
#define QMI8658_CTRL3             0x04U
#define QMI8658_CTRL5             0x06U
#define QMI8658_CTRL7             0x08U
#define QMI8658_CTRL8             0x09U
#define QMI8658_CTRL9             0x0AU
#define QMI8658_STATUS0           0x2EU
#define QMI8658_TEMP_L            0x33U
#define QMI8658_ACCEL_X_L         0x35U
#define QMI8658_RESET             0x60U

/* Official V1.2 configuration: +/-8g, +/-1024 dps, 250 Hz. */
#define QMI8658_ACCEL_SENSITIVITY 4096.0f
#define QMI8658_GYRO_SENSITIVITY  32.0f

static uint8_t qmi8658_address = 0;

static HAL_StatusTypeDef qmi8658_write(uint8_t reg, uint8_t value) {
    return HAL_I2C_Mem_Write(&hi2c2,
                             (uint16_t)qmi8658_address << 1,
                             reg,
                             I2C_MEMADD_SIZE_8BIT,
                             &value,
                             1,
                             100);
}

static HAL_StatusTypeDef qmi8658_read(uint8_t reg, uint8_t *data, uint16_t length) {
    return HAL_I2C_Mem_Read(&hi2c2,
                            (uint16_t)qmi8658_address << 1,
                            reg,
                            I2C_MEMADD_SIZE_8BIT,
                            data,
                            length,
                            100);
}

static int qmi8658_write_checked(uint8_t reg, uint8_t value) {
    return qmi8658_write(reg, value) == HAL_OK ? 0 : -1;
}

static int qmi8658_read_checked(uint8_t reg, uint8_t *data, uint16_t length) {
    return qmi8658_read(reg, data, length) == HAL_OK ? 0 : -1;
}

static int16_t qmi8658_le_i16(const uint8_t *data) {
    return (int16_t)(((uint16_t)data[1] << 8) | data[0]);
}

static void imu_failure(uint8_t status, int error, uint32_t now) {
    imu_initialized = false;
    imu_status = status;
    imu_last_error = error;
    imu_error_count++;
    last_imu_update_time = now;
    next_imu_init_attempt = now + IMU_RETRY_PERIOD_MS;
}

// ============================================================================
// IMU INITIALIZATION
// ============================================================================

int IMU_Init(void) {
    const uint8_t candidate_addresses[] = { QMI8658_ADDR_LOW, QMI8658_ADDR_HIGH };
    bool device_found = false;
    imu_initialized = false;
    imu_status = IMU_STATUS_UNAVAILABLE;
    imu_device_address = 0;
    imu_who_am_i = 0;
    imu_last_error = -2;
    uint32_t init_time = HAL_GetTick();
    /* Give the onboard sensor rail time to settle after power is applied or
     * after a watchdog/SWD restart. */
    HAL_Delay(100);
    for (size_t i = 0;
         i < (sizeof(candidate_addresses) / sizeof(candidate_addresses[0]));
         ++i) {
        qmi8658_address = candidate_addresses[i];
        if (HAL_I2C_IsDeviceReady(&hi2c2,
                                  (uint16_t)qmi8658_address << 1,
                                  2,
                                  20) ==
            HAL_OK) {
            imu_device_address = qmi8658_address;
            uint8_t who_am_i = 0;
            if (qmi8658_read_checked(QMI8658_WHO_AM_I_REG, &who_am_i, 1) != 0) {
                imu_last_error = -3;
                continue;
            }
            imu_who_am_i = who_am_i;
            if (who_am_i != QMI8658_WHO_AM_I_VALUE) {
                imu_last_error = -4;
                continue;
            }
            device_found = true;
            break;
        }
    }

    /* Probe both official QMI8658 address straps before configuration. */
    if (!device_found) {
        imu_failure(
            imu_last_error == -2 ? IMU_STATUS_UNAVAILABLE : IMU_STATUS_ERROR,
            imu_last_error,
            init_time);
        return imu_last_error;
    }
    
    /* This is the initialization sequence used by Hiwonder's V1.2 source. */
    if (qmi8658_write_checked(QMI8658_CTRL7, 0x00) != 0 ||
        qmi8658_write_checked(QMI8658_RESET, 0xB0) != 0) {
        imu_failure(IMU_STATUS_ERROR, -5, init_time);
        return -5;
    }
    HAL_Delay(10);

    /* The vendor sample performs a 2.2-second on-demand calibration here.
     * That blocks the motor/UART protocol task during boot, so production
     * startup leaves calibration at the sensor's normal zero-offset state and
     * begins streaming immediately. */
    if (qmi8658_write_checked(QMI8658_CTRL1, 0x78) != 0 ||
        qmi8658_write_checked(QMI8658_CTRL8, 0xC0) != 0) {
        imu_failure(IMU_STATUS_ERROR, -5, init_time);
        return -5;
    }

    /* CTRL2: +/-8g at 250Hz; CTRL3: +/-1024dps at 250Hz. */
    if (qmi8658_write_checked(QMI8658_CTRL2, 0x25) != 0 ||
        qmi8658_write_checked(QMI8658_CTRL3, 0x65) != 0) {
        imu_failure(IMU_STATUS_ERROR, -5, init_time);
        return -5;
    }

    uint8_t ctrl5 = 0;
    if (qmi8658_read_checked(QMI8658_CTRL5, &ctrl5, 1) != 0 ||
        qmi8658_write_checked(QMI8658_CTRL5, (uint8_t)(ctrl5 & (uint8_t)~0x11U)) != 0 ||
        qmi8658_write_checked(QMI8658_CTRL7, 0x03) != 0) {
        imu_failure(IMU_STATUS_ERROR, -5, init_time);
        return -5;
    }
    HAL_Delay(20);

    uint8_t status = 0;
    uint8_t startup_data[12] = {0};
    if (qmi8658_read_checked(QMI8658_STATUS0, &status, 1) != 0 ||
        qmi8658_read_checked(QMI8658_ACCEL_X_L, startup_data, sizeof(startup_data)) != 0) {
        imu_failure(IMU_STATUS_ERROR, -6, init_time);
        return -6;
    }
    (void)status;

    imu_initialized = true;
    imu_status = IMU_STATUS_READY;
    imu_sample_count = 0;
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
    
    /* QMI8658 exposes little-endian acceleration and gyro samples in one
     * contiguous 12-byte block beginning at 0x35. */
    uint8_t status = 0;
    uint8_t sensor_data[12] = {0};
    if (qmi8658_read_checked(QMI8658_STATUS0, &status, 1) != 0) {
        /* Recover from a transient I2C fault instead of publishing stale
         * values forever. The next bounded retry re-probes both addresses. */
        imu_failure(IMU_STATUS_ERROR, -7, current_time);
        return imu_last_error; // Sensor read failed
    }
    if ((status & 0x03U) == 0U) {
        return -2; // QMI8658 has not completed the next accel+gyro sample yet.
    }
    if (qmi8658_read_checked(QMI8658_ACCEL_X_L, sensor_data, sizeof(sensor_data)) != 0) {
        imu_failure(IMU_STATUS_ERROR, -7, current_time);
        return imu_last_error;
    }
    
    (void)status; /* A sample read is valid after the enabled 250 Hz stream. */
    const float gravity = 9.807f;
    const float degrees_to_radians = 0.017453292519943f;
    for (size_t axis = 0; axis < 3; ++axis) {
        int16_t raw_accel = qmi8658_le_i16(&sensor_data[axis * 2]);
        int16_t raw_gyro = qmi8658_le_i16(&sensor_data[6 + axis * 2]);
        /* Official Hiwonder scaling: +/-8g => 4096 counts/g and
         * +/-1024 dps => 32 counts/(degree/s). */
        accel[axis] = ((float)raw_accel * gravity) / QMI8658_ACCEL_SENSITIVITY;
        gyro[axis] = ((float)raw_gyro * degrees_to_radians) / QMI8658_GYRO_SENSITIVITY;
    }
    if (!isfinite(accel[0]) || !isfinite(accel[1]) ||
        !isfinite(accel[2]) || !isfinite(gyro[0]) ||
        !isfinite(gyro[1]) || !isfinite(gyro[2])) {
        imu_failure(IMU_STATUS_ERROR, -8, current_time);
        return -8;
    }
    imu_sample_count++;
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
    
    /* The bridge publishes raw SI acceleration and angular velocity. Do not
     * fabricate orientation from an uninitialized fusion state. */
    (void)rpy;
    (void)quat;
    return -2;
}

// ============================================================================
// IMU STATUS CHECKS
// ============================================================================

bool IMU_IsReady(void) {
    return imu_initialized;
}

void IMU_GetDiagnostics(IMUDiagnostics *diagnostics) {
    if (diagnostics == NULL) {
        return;
    }
    diagnostics->state = imu_status;
    diagnostics->address = imu_device_address;
    diagnostics->who_am_i = imu_who_am_i;
    diagnostics->sample_count = imu_sample_count;
    diagnostics->error_count = imu_error_count;
    diagnostics->last_error = imu_last_error;
}

int IMU_GetTemperature(float *temp) {
    if (!imu_initialized) {
        return -1;
    }
    
    uint8_t raw_temp[2] = {0};
    if (qmi8658_read_checked(QMI8658_TEMP_L, raw_temp, sizeof(raw_temp)) != 0) {
        return -1;
    }
    *temp = (float)qmi8658_le_i16(raw_temp) / 256.0f;
    return 0;
}
