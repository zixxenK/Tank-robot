/**
 * @file hc_sr04.h
 * @brief Non-blocking HC-SR04 driver on PC8 trigger / PC9 echo.
 */

#ifndef HC_SR04_H
#define HC_SR04_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint16_t distance_mm;
    uint16_t echo_us;
    bool valid;
} HcSr04Measurement;

void hc_sr04_init(void);
void hc_sr04_service(void);
void hc_sr04_echo_edge(void);
bool hc_sr04_get_measurement(HcSr04Measurement *measurement);

#endif /* HC_SR04_H */
