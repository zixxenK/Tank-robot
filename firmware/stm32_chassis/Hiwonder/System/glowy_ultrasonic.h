/**
 * @file glowy_ultrasonic.h
 * @brief Hiwonder Glowy RGB ultrasonic sensor on the shared I2C2 bus.
 *
 * The Glowy module is an I2C peripheral with no MCU pulse-timing path.
 * It uses the controller's 4-pin I2C peripheral connector:
 * 5V, GND, SDA, SCL.  Its 7-bit address is 0x77 and register 0 returns a
 * little-endian distance in millimetres.
 */

#ifndef GLOWY_ULTRASONIC_H
#define GLOWY_ULTRASONIC_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint16_t distance_mm;
    bool valid;
    uint8_t status;
} GlowyUltrasonicMeasurement;

typedef struct {
    uint32_t read_count;
    uint32_t valid_count;
    uint32_t error_count;
} GlowyUltrasonicDiagnostics;

void glowy_ultrasonic_init(void);
bool glowy_ultrasonic_read(GlowyUltrasonicMeasurement *measurement);
uint8_t glowy_ultrasonic_get_status(void);
void glowy_ultrasonic_get_diagnostics(GlowyUltrasonicDiagnostics *diagnostics);

#endif /* GLOWY_ULTRASONIC_H */
