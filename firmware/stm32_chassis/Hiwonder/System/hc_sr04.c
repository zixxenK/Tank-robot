/**
 * @file hc_sr04.c
 * @brief Non-blocking HC-SR04 timing driver.
 *
 * PC8 emits a 10 us trigger pulse. PC9 captures both echo edges through EXTI
 * and DWT->CYCCNT provides microsecond timing without blocking the motor task.
 */

#include "hc_sr04.h"

#include "main.h"
#include "stm32f4xx.h"

#define HC_SR04_MIN_INTERVAL_MS 60U
#define HC_SR04_TIMEOUT_MS 35U
#define HC_SR04_MIN_ECHO_US 100U
#define HC_SR04_MAX_ECHO_US 25000U

static volatile uint32_t echo_start_cycles;
static volatile uint32_t last_trigger_ms;
static volatile uint32_t timeout_deadline_ms;
static volatile uint16_t latest_echo_us;
static volatile uint16_t latest_distance_mm;
static volatile bool waiting_for_rise;
static volatile bool measurement_active;
static volatile bool measurement_ready;

static uint32_t cycles_per_us(void)
{
    return SystemCoreClock / 1000000U;
}

static void delay_us(uint32_t microseconds)
{
    uint32_t start = DWT->CYCCNT;
    uint32_t cycles = microseconds * cycles_per_us();
    while ((uint32_t)(DWT->CYCCNT - start) < cycles) {
        /* Deliberately busy-wait for only the 10 us trigger pulse. */
    }
}

void hc_sr04_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    HAL_GPIO_WritePin(HC_SR04_TRIG_GPIO_Port,
                      HC_SR04_TRIG_Pin,
                      GPIO_PIN_RESET);
    waiting_for_rise = false;
    measurement_active = false;
    measurement_ready = false;
    latest_echo_us = 0U;
    latest_distance_mm = 0U;
    last_trigger_ms = HAL_GetTick() - HC_SR04_MIN_INTERVAL_MS;
}

void hc_sr04_service(void)
{
    uint32_t now = HAL_GetTick();

    if (measurement_active &&
        (uint32_t)(now - timeout_deadline_ms) < 0x80000000U) {
        measurement_active = false;
        waiting_for_rise = false;
    }
    if (measurement_active ||
        (uint32_t)(now - last_trigger_ms) < HC_SR04_MIN_INTERVAL_MS) {
        return;
    }

    measurement_active = true;
    waiting_for_rise = true;
    measurement_ready = false;
    last_trigger_ms = now;
    timeout_deadline_ms = now + HC_SR04_TIMEOUT_MS;

    HAL_GPIO_WritePin(HC_SR04_TRIG_GPIO_Port,
                      HC_SR04_TRIG_Pin,
                      GPIO_PIN_SET);
    delay_us(10U);
    HAL_GPIO_WritePin(HC_SR04_TRIG_GPIO_Port,
                      HC_SR04_TRIG_Pin,
                      GPIO_PIN_RESET);
}

void hc_sr04_echo_edge(void)
{
    if (!measurement_active) {
        return;
    }

    if (HAL_GPIO_ReadPin(HC_SR04_ECHO_GPIO_Port, HC_SR04_ECHO_Pin) ==
        GPIO_PIN_SET) {
        if (waiting_for_rise) {
            echo_start_cycles = DWT->CYCCNT;
            waiting_for_rise = false;
        }
        return;
    }

    if (!waiting_for_rise) {
        uint32_t elapsed_cycles = DWT->CYCCNT - echo_start_cycles;
        uint32_t echo_us = elapsed_cycles / cycles_per_us();
        measurement_active = false;
        if (echo_us >= HC_SR04_MIN_ECHO_US &&
            echo_us <= HC_SR04_MAX_ECHO_US) {
            latest_echo_us = (uint16_t)echo_us;
            latest_distance_mm = (uint16_t)((echo_us * 343U) / 2000U);
            measurement_ready = true;
        }
        waiting_for_rise = false;
    }
}

bool hc_sr04_get_measurement(HcSr04Measurement *measurement)
{
    if (measurement == NULL || !measurement_ready) {
        return false;
    }
    measurement->echo_us = latest_echo_us;
    measurement->distance_mm = latest_distance_mm;
    measurement->valid = true;
    measurement_ready = false;
    return true;
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == HC_SR04_ECHO_Pin) {
        hc_sr04_echo_edge();
    }
}
