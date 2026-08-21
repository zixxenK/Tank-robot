/**
 * @file battery_integration.h
 * @brief Battery/ADC integration with filter priming
 */

#ifndef BATTERY_INTEGRATION_H
#define BATTERY_INTEGRATION_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

// ============================================================================
// FUNCTION PROTOTYPES
// ============================================================================

/**
 * @brief Initialize battery monitoring with filter priming
 * @return 0 on success, negative on error
 * 
 * Initializes ADC with:
 * - Two-rank DMA mode (battery voltage plus internal VREFINT)
 * - Filter priming with 10 samples to prevent startup false positives
 * - Voltage divider scaling (11x ratio)
 * - Moving average filter (5% new, 95% old)
 */
int Battery_Init(void);

/**
 * @brief Update battery reading from ADC
 * @return 0 on success, negative on error
 * 
 * Processes ADC DMA buffer data and applies moving average filter.
 * Call this periodically (e.g., in telemetry loop at 10-50Hz).
 */
int Battery_Update(void);

/**
 * @brief Get current battery voltage
 * @return Battery voltage in volts
 */
float Battery_GetVoltage(void);

/**
 * @brief Get current battery current
 * @return Battery current in amps (0.0f if no current sensing)
 */
float Battery_GetCurrent(void);

/**
 * @brief Check if battery voltage is low
 * @return true if voltage < 10.5V (documented 11.1V/3S pack warning)
 */
bool Battery_IsLowVoltage(void);

/**
 * @brief Check if battery voltage is critical
 * @return true if voltage < 9.5V (documented 11.1V/3S pack cutoff)
 */
bool Battery_IsCriticalVoltage(void);

/**
 * @brief Check if battery monitoring is ready
 * @return true if initialized and filter is primed
 */
bool Battery_IsReady(void);

/**
 * @brief Check if current sensing is valid and available
 * @return true if current sensor is present and providing valid data
 */
bool Battery_IsCurrentValid(void);

#ifdef __cplusplus
}
#endif

#endif /* BATTERY_INTEGRATION_H */
