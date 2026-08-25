/**
 * @file status_integration.h
 * @brief Buzzer and LED status indicators integration
 */

#ifndef STATUS_INTEGRATION_H
#define STATUS_INTEGRATION_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

// ============================================================================
// FUNCTION PROTOTYPES
// ============================================================================

/**
 * @brief Initialize status peripherals (buzzer and LED)
 * @return 0 on success, negative on error
 */
int Status_Init(void);

/**
 * @brief Update status peripheral state machines
 * @param period_ms Time since last update in milliseconds
 * 
 * Call this periodically (e.g., every 10ms) to handle buzzer/LED timing.
 */
void Status_Update(uint32_t period_ms);

// ============================================================================
// EMERGENCY AUDIO INDICATIONS
// ============================================================================

/**
 * @brief Trigger emergency beep sequence
 * Aggressive pattern for critical failures
 */
void Status_EmergencyBeep(void);

/**
 * @brief Trigger communication lost beep pattern
 * Indicates lost connection to ROCK64
 */
void Status_CommunicationLostBeep(void);

/**
 * @brief Trigger low battery warning beep
 * Indicates battery voltage below threshold
 */
void Status_LowBatteryBeep(void);

/**
 * @brief Trigger system OK acknowledgment beep
 * Indicates normal operation
 */
void Status_OKBeep(void);

// ============================================================================
// LED STATUS INDICATIONS
// ============================================================================

/**
 * @brief Set LED to normal operation (solid on)
 */
void Status_SetLEDNormal(void);

/**
 * @brief Set LED to warning mode (slow flash)
 */
void Status_SetLEDWarning(void);

/**
 * @brief Set LED to emergency mode (fast flash)
 */
void Status_SetLEDEmergency(void);

/**
 * @brief Turn LED off
 */
void Status_SetLEDOff(void);

// ============================================================================
// SYSTEM STARTUP INDICATION
// ============================================================================

/**
 * @brief Execute startup indication sequence
 * Visual and audible indication that system is ready
 */
void Status_StartupSequence(void);

/** Start the Sea Shanty 2 melody after the buzzer has been initialized. */
void Status_PlayStartupSong(void);

#ifdef __cplusplus
}
#endif

#endif /* STATUS_INTEGRATION_H */
