/**
 * @file sg90_servo.c
 * @brief Interrupt-driven SG90 pulse generation on J1 / PA11.
 *
 * TIM13 runs at 1 MHz with a 20 ms period.  PA11 remains an ordinary GPIO:
 * the update interrupt drives the rising edge and CC1 drives the falling
 * edge.  This deliberately avoids the factory heap-backed PWM-servo code and
 * never touches PC8/PA12, which belong to the HC-SR04 production path.
 */

#include "sg90_servo.h"

#include "main.h"
#include "tim.h"

#define SG90_FRAME_MS 20U

typedef struct {
    volatile bool enabled;
    volatile uint16_t current_pulse_us;
    volatile uint16_t start_pulse_us;
    volatile uint16_t target_pulse_us;
    volatile uint16_t transition_steps;
    volatile uint16_t transition_step;
} SG90ServoState;

static SG90ServoState servo_state;

static uint16_t interpolated_pulse(uint16_t step)
{
    int32_t start = (int32_t)servo_state.start_pulse_us;
    int32_t delta = (int32_t)servo_state.target_pulse_us - start;
    int32_t pulse = start;

    if (servo_state.transition_steps != 0U) {
        pulse += (delta * (int32_t)step) /
                 (int32_t)servo_state.transition_steps;
    }
    if (pulse < (int32_t)SG90_SERVO_MIN_PULSE_US) {
        pulse = (int32_t)SG90_SERVO_MIN_PULSE_US;
    } else if (pulse > (int32_t)SG90_SERVO_MAX_PULSE_US) {
        pulse = (int32_t)SG90_SERVO_MAX_PULSE_US;
    }
    return (uint16_t)pulse;
}

static void advance_transition(void)
{
    if (servo_state.transition_step < servo_state.transition_steps) {
        servo_state.transition_step++;
        servo_state.current_pulse_us =
            interpolated_pulse(servo_state.transition_step);
    } else {
        servo_state.current_pulse_us = servo_state.target_pulse_us;
    }
    __HAL_TIM_SET_COMPARE(&htim13,
                          TIM_CHANNEL_1,
                          servo_state.current_pulse_us);
}

void SG90Servo_Init(void)
{
    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    __HAL_TIM_DISABLE(&htim13);
    __HAL_TIM_DISABLE_IT(&htim13, TIM_IT_UPDATE | TIM_IT_CC1);
    TIM_CCxChannelCmd(htim13.Instance, TIM_CHANNEL_1, TIM_CCx_DISABLE);
    __HAL_TIM_SET_COUNTER(&htim13, 0U);
    __HAL_TIM_SET_AUTORELOAD(&htim13, 19999U);
    __HAL_TIM_SET_COMPARE(&htim13,
                          TIM_CHANNEL_1,
                          SG90_SERVO_NEUTRAL_PULSE_US);
    (void)HAL_TIM_GenerateEvent(&htim13, TIM_EVENTSOURCE_UPDATE);
    __HAL_TIM_CLEAR_FLAG(&htim13, TIM_FLAG_UPDATE | TIM_FLAG_CC1);

    HAL_GPIO_WritePin(PWM_SERVO_1_GPIO_Port,
                      PWM_SERVO_1_Pin,
                      GPIO_PIN_RESET);

    servo_state.enabled = false;
    servo_state.current_pulse_us = SG90_SERVO_NEUTRAL_PULSE_US;
    servo_state.start_pulse_us = SG90_SERVO_NEUTRAL_PULSE_US;
    servo_state.target_pulse_us = SG90_SERVO_NEUTRAL_PULSE_US;
    servo_state.transition_steps = 0U;
    servo_state.transition_step = 0U;

    if (primask == 0U) {
        __enable_irq();
    }
}

bool SG90Servo_Command(uint8_t channel,
                       uint16_t pulse_us,
                       uint16_t duration_ms)
{
    if (channel != SG90_SERVO_CHANNEL ||
        pulse_us < SG90_SERVO_MIN_PULSE_US ||
        pulse_us > SG90_SERVO_MAX_PULSE_US ||
        duration_ms < SG90_SERVO_MIN_DURATION_MS ||
        duration_ms > SG90_SERVO_MAX_DURATION_MS) {
        return false;
    }

    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    servo_state.start_pulse_us = servo_state.current_pulse_us;
    servo_state.target_pulse_us = pulse_us;
    servo_state.transition_steps =
        (uint16_t)(((uint32_t)duration_ms + SG90_FRAME_MS - 1U) /
                   SG90_FRAME_MS);
    servo_state.transition_step = 0U;

    if (!servo_state.enabled) {
        servo_state.enabled = true;
        /* Apply the first bounded transition step before raising PA11 so the
         * first generated pulse is already moving toward the request. */
        advance_transition();
        __HAL_TIM_SET_COUNTER(&htim13, 0U);
        __HAL_TIM_CLEAR_FLAG(&htim13, TIM_FLAG_UPDATE | TIM_FLAG_CC1);
        HAL_GPIO_WritePin(PWM_SERVO_1_GPIO_Port,
                          PWM_SERVO_1_Pin,
                          GPIO_PIN_SET);
        TIM_CCxChannelCmd(htim13.Instance,
                         TIM_CHANNEL_1,
                         TIM_CCx_ENABLE);
        __HAL_TIM_ENABLE_IT(&htim13, TIM_IT_UPDATE | TIM_IT_CC1);
        __HAL_TIM_ENABLE(&htim13);
    }

    if (primask == 0U) {
        __enable_irq();
    }
    return true;
}

void SG90Servo_PeriodElapsedCallback(void)
{
    if (!servo_state.enabled) {
        HAL_GPIO_WritePin(PWM_SERVO_1_GPIO_Port,
                          PWM_SERVO_1_Pin,
                          GPIO_PIN_RESET);
        return;
    }

    advance_transition();
    /* If interrupts were masked past the compare point, skip this frame
     * instead of raising PA11 for nearly a full 20 ms period. */
    if (__HAL_TIM_GET_COUNTER(&htim13) < servo_state.current_pulse_us) {
        HAL_GPIO_WritePin(PWM_SERVO_1_GPIO_Port,
                          PWM_SERVO_1_Pin,
                          GPIO_PIN_SET);
    } else {
        HAL_GPIO_WritePin(PWM_SERVO_1_GPIO_Port,
                          PWM_SERVO_1_Pin,
                          GPIO_PIN_RESET);
    }
}

void SG90Servo_PulseElapsedCallback(void)
{
    HAL_GPIO_WritePin(PWM_SERVO_1_GPIO_Port,
                      PWM_SERVO_1_Pin,
                      GPIO_PIN_RESET);
}
