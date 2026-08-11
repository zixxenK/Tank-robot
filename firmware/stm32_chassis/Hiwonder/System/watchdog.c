#include "watchdog.h"

#include "stm32f4xx_hal.h"

// Watchdog stub - IWDG not available in factory configuration
static bool watchdog_initialized;
static bool watchdog_reset_detected;
static bool reset_cause_captured;

void Watchdog_CaptureResetCause(void) {
    watchdog_reset_detected = false;
    reset_cause_captured = true;
}

bool Watchdog_Init(void) {
    if (watchdog_initialized) {
        return true;
    }

    if (!reset_cause_captured) {
        Watchdog_CaptureResetCause();
    }

    watchdog_initialized = true;
    return true;
}

void Watchdog_Refresh(void) {
    // Stub - no actual watchdog refresh
}

bool Watchdog_WasReset(void) {
    return watchdog_reset_detected;
}