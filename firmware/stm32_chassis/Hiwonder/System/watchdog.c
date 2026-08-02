#include "watchdog.h"

#include "stm32f4xx_hal.h"

static IWDG_HandleTypeDef watchdog_handle;
static bool watchdog_initialized;
static bool watchdog_reset_detected;
static bool reset_cause_captured;

void Watchdog_CaptureResetCause(void) {
    watchdog_reset_detected =
        (__HAL_RCC_GET_FLAG(RCC_FLAG_IWDGRST) != RESET);
    __HAL_RCC_CLEAR_RESET_FLAGS();
    reset_cause_captured = true;
}

bool Watchdog_Init(void) {
    if (watchdog_initialized) {
        return true;
    }

    if (!reset_cause_captured) {
        Watchdog_CaptureResetCause();
    }

#ifdef DEBUG
    __HAL_DBGMCU_FREEZE_IWDG();
#endif

    watchdog_handle.Instance = IWDG;
    watchdog_handle.Init.Prescaler = IWDG_PRESCALER_32;
    watchdog_handle.Init.Reload = 999U;

    if (HAL_IWDG_Init(&watchdog_handle) != HAL_OK) {
        return false;
    }

    watchdog_initialized = true;
    return true;
}

void Watchdog_Refresh(void) {
    if (watchdog_initialized) {
        (void)HAL_IWDG_Refresh(&watchdog_handle);
    }
}

bool Watchdog_WasReset(void) {
    return watchdog_reset_detected;
}