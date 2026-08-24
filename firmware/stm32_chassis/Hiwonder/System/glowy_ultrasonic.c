/**
 * @file glowy_ultrasonic.c
 * @brief Hiwonder Glowy RGB ultrasonic sensor I2C driver.
 */

#include "glowy_ultrasonic.h"

#include <stddef.h>

#include "i2c.h"

#define GLOWY_ULTRASONIC_ADDRESS       0x77U
#define GLOWY_ULTRASONIC_DISTANCE_REG  0x00U
#define GLOWY_ULTRASONIC_MIN_MM        20U
#define GLOWY_ULTRASONIC_MAX_MM        4000U
#define GLOWY_ULTRASONIC_RETRY_MS      1000U

enum {
    GLOWY_STATUS_UNAVAILABLE = 0,
    GLOWY_STATUS_VALID = 1,
    GLOWY_STATUS_OUT_OF_RANGE = 2,
    GLOWY_STATUS_READ_ERROR = 3,
};

static bool sensor_ready = false;
static uint32_t next_probe_time = 0;
static uint8_t sensor_status = GLOWY_STATUS_UNAVAILABLE;
static GlowyUltrasonicDiagnostics sensor_diagnostics = {0};

static bool probe_sensor(void)
{
    if (HAL_I2C_IsDeviceReady(&hi2c2,
                              GLOWY_ULTRASONIC_ADDRESS << 1,
                              2,
                              20) != HAL_OK) {
        sensor_diagnostics.error_count++;
        sensor_ready = false;
        sensor_status = GLOWY_STATUS_UNAVAILABLE;
        next_probe_time = HAL_GetTick() + GLOWY_ULTRASONIC_RETRY_MS;
        return false;
    }

    sensor_ready = true;
    sensor_status = GLOWY_STATUS_OUT_OF_RANGE;
    next_probe_time = HAL_GetTick() + GLOWY_ULTRASONIC_RETRY_MS;
    return true;
}

void glowy_ultrasonic_init(void)
{
    sensor_ready = false;
    sensor_status = GLOWY_STATUS_UNAVAILABLE;
    sensor_diagnostics = (GlowyUltrasonicDiagnostics){0};
    next_probe_time = 0;
    (void)probe_sensor();
}

bool glowy_ultrasonic_read(GlowyUltrasonicMeasurement *measurement)
{
    if (measurement == NULL) {
        return false;
    }

    measurement->distance_mm = 0;
    measurement->valid = false;
    measurement->status = sensor_status;

    uint32_t now = HAL_GetTick();
    if (!sensor_ready) {
        if ((int32_t)(now - next_probe_time) >= 0) {
            (void)probe_sensor();
        }
        measurement->status = sensor_status;
        return false;
    }

    uint8_t raw_distance[2] = {0, 0};
    HAL_StatusTypeDef result = HAL_I2C_Mem_Read(&hi2c2,
                                                GLOWY_ULTRASONIC_ADDRESS << 1,
                                                GLOWY_ULTRASONIC_DISTANCE_REG,
                                                I2C_MEMADD_SIZE_8BIT,
                                                raw_distance,
                                                sizeof(raw_distance),
                                                100);
    sensor_diagnostics.read_count++;
    if (result != HAL_OK) {
        sensor_diagnostics.error_count++;
        sensor_ready = false;
        sensor_status = GLOWY_STATUS_READ_ERROR;
        next_probe_time = now + GLOWY_ULTRASONIC_RETRY_MS;
        measurement->status = sensor_status;
        return false;
    }

    uint16_t distance_mm = (uint16_t)raw_distance[0] |
                           ((uint16_t)raw_distance[1] << 8);
    measurement->distance_mm = distance_mm;
    if (distance_mm < GLOWY_ULTRASONIC_MIN_MM ||
        distance_mm > GLOWY_ULTRASONIC_MAX_MM) {
        sensor_status = GLOWY_STATUS_OUT_OF_RANGE;
        measurement->status = sensor_status;
        return false;
    }

    sensor_diagnostics.valid_count++;
    sensor_status = GLOWY_STATUS_VALID;
    measurement->valid = true;
    measurement->status = sensor_status;
    return true;
}

uint8_t glowy_ultrasonic_get_status(void)
{
    return sensor_status;
}

void glowy_ultrasonic_get_diagnostics(GlowyUltrasonicDiagnostics *diagnostics)
{
    if (diagnostics != NULL) {
        *diagnostics = sensor_diagnostics;
    }
}
