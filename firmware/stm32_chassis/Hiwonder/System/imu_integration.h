/**
 * @file imu_integration.h
 * @brief QMI8658 integration wrapper with a fixed 50 Hz acquisition period
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
 * @brief Initialize the project's QMI8658 runtime path
 * @return 0 on success, negative on error
 * 
 * Initializes the project's QMI8658 runtime path with the program-example
 * configuration. Hiwonder's live product/hardware pages still label the
 * physical sensor MPU6050, so readiness requires the runtime identity gate:
 * - 250Hz sensor output (read by the bridge at 50Hz)
 * - ±8g accelerometer range
 * - ±1024°/s gyroscope range
 */
int IMU_Init(void);

/**
 * @brief Update the QMI8658 reading at the fixed acquisition cadence
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
 * @brief Get orientation data (currently unsupported by the raw QMI path)
 * @param rpy Output array for roll-pitch-yaw [roll, pitch, yaw] in radians
 * @param quat Output array for quaternion [w, x, y, z]
 * @return -1 if the sensor is unavailable; -2 because the raw-sensor-only
 *         production path has no fusion state
 */
int IMU_GetOrientation(float *rpy, float *quat);

/**
 * @brief Check if IMU is initialized and ready
 * @return true if ready, false otherwise
 */
bool IMU_IsReady(void);

/** @brief Copy explicit IMU-path readiness and bus diagnostics. */
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
