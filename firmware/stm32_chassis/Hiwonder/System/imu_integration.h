/**
 * @file imu_integration.h
 * @brief IMU integration wrapper with fixed delta time for Madgwick filter
 */

#ifndef IMU_INTEGRATION_H
#define IMU_INTEGRATION_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

#define IMU_STATUS_UNAVAILABLE 0U
#define IMU_STATUS_READY       1U
#define IMU_STATUS_ERROR       2U

typedef struct {
    uint8_t state;
    uint8_t address;
    uint16_t who_am_i;
    uint32_t sample_count;
    uint32_t error_count;
    int32_t last_error;
} IMUDiagnostics;

// ============================================================================
// FUNCTION PROTOTYPES
// ============================================================================

/**
 * @brief Initialize IMU sensor with fixed delta time configuration
 * @return 0 on success, negative on error
 * 
 * Initializes MPU6050 with:
 * - 50Hz update rate (fixed dt = 0.02s)
 * - ±4g accelerometer range
 * - ±1000°/s gyroscope range
 * - 20Hz low-pass filter
 */
int IMU_Init(void);

/**
 * @brief Update IMU sensor reading with fixed delta time
 * @param accel Output array for accelerometer [x, y, z] in m/s²
 * @param gyro Output array for gyroscope [x, y, z] in rad/s
 * @return 0 on success, negative on error
 * 
 * CRITICAL: This function is rate-limited to 50Hz (20ms period)
 * to prevent I2C blocking in the 100Hz motor control loop.
 * Only call this from the telemetry burst task, not motor control.
 */
int IMU_Update(float *accel, float *gyro);

/**
 * @brief Get orientation data (Euler angles and quaternion)
 * @param rpy Output array for roll-pitch-yaw [roll, pitch, yaw] in radians
 * @param quat Output array for quaternion [w, x, y, z]
 * @return 0 on success, negative on error
 */
int IMU_GetOrientation(float *rpy, float *quat);

/**
 * @brief Check if IMU is initialized and ready
 * @return true if ready, false otherwise
 */
bool IMU_IsReady(void);

/** @brief Copy explicit onboard MPU6050 readiness and bus diagnostics. */
void IMU_GetDiagnostics(IMUDiagnostics *diagnostics);

/**
 * @brief Get IMU temperature reading
 * @param temp Output temperature in degrees Celsius
 * @return 0 on success, negative on error
 */
int IMU_GetTemperature(float *temp);

#ifdef __cplusplus
}
#endif

#endif /* IMU_INTEGRATION_H */
