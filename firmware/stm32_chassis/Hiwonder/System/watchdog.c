#include "watchdog.h"

#include "stm32f4xx_hal.h"

/*
 * The IWDG is clocked from the independent LSI oscillator, so it continues
 * to run if the application clock or RTOS becomes unhealthy.  The selected
 * prescaler/reload gives approximately eight seconds at the nominal 32 kHz
 * LSI frequency.  Refreshing it is deliberately owned by the packed UART
 * protocol task, which is the task responsible for the motor command loop.
 */
static bool watchdog_initialized;
static bool watchdog_reset_detected;
static bool reset_cause_captured;

void Watchdog_CaptureResetCause(void) {
    watchdog_reset_detected = (__HAL_RCC_GET_FLAG(RCC_FLAG_IWDGRST) != RESET);
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

    /* The repository intentionally does not vendor stm32f4xx_hal_iwdg.c.
     * These register writes are the reference STM32F4 IWDG sequence: unlock
     * configuration, select /64, load the maximum ~8 s timeout, then start. */
    IWDG->KR = 0x5555U;
    IWDG->PR = 4U;       /* /64 from the nominal 32 kHz LSI */
    IWDG->RLR = 0x0FFFU;
    IWDG->KR = 0xCCCCU;  /* start IWDG and its independent LSI clock */

    watchdog_initialized = true;
    return true;
}

void Watchdog_Refresh(void) {
    if (watchdog_initialized) {
        IWDG->KR = 0xAAAAU;
    }
}

bool Watchdog_WasReset(void) {
    return watchdog_reset_detected;
}
