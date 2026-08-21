/**
 * @file sg90_servo.h
 * @brief Heap-free 50 Hz SG90 driver for the production J1/PA11 output.
 */

#ifndef SG90_SERVO_H
#define SG90_SERVO_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stdint.h>

#define SG90_SERVO_CHANNEL            0U
#define SG90_SERVO_MIN_PULSE_US     1000U
#define SG90_SERVO_NEUTRAL_PULSE_US 1500U
#define SG90_SERVO_MAX_PULSE_US     2000U
#define SG90_SERVO_MIN_DURATION_MS    20U
#define SG90_SERVO_MAX_DURATION_MS  5000U

/** Keep PA11 low and TIM13 stopped until the first accepted command. */
void SG90Servo_Init(void);

/**
 * Validate and apply a bounded SG90 command.
 *
 * The requested transition is linearly spread across 20 ms servo frames.
 * Returns false without changing the output for an invalid command.
 */
bool SG90Servo_Command(uint8_t channel,
                       uint16_t pulse_us,
                       uint16_t duration_ms);

/** TIM13 update callback: start a pulse and advance the bounded transition. */
void SG90Servo_PeriodElapsedCallback(void);

/** TIM13 CC1 callback: finish the current PA11 pulse. */
void SG90Servo_PulseElapsedCallback(void);

#ifdef __cplusplus
}
#endif

#endif /* SG90_SERVO_H */
