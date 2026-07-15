/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Rock64 Ranger - STM32 Chassis Controller
  *
  ******************************************************************************
  */

#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"

/* Board-level pin mapping (cross-check with Hiwonder wiki before flashing) */
#define ROCK64_UART_INSTANCE          USART2
#define ROCK64_UART_TX_PIN            GPIO_PIN_2
#define ROCK64_UART_TX_PORT           GPIOA
#define ROCK64_UART_RX_PIN            GPIO_PIN_3
#define ROCK64_UART_RX_PORT           GPIOA

#define MPU6050_I2C_INSTANCE          I2C1
#define MPU6050_I2C_SCL_PIN           GPIO_PIN_6
#define MPU6050_I2C_SCL_PORT          GPIOB
#define MPU6050_I2C_SDA_PIN           GPIO_PIN_7
#define MPU6050_I2C_SDA_PORT          GPIOB

#define MOTOR_PWM_TIMER               TIM3
#define MOTOR_LEFT_PWM_CHANNEL        TIM_CHANNEL_1
#define MOTOR_RIGHT_PWM_CHANNEL       TIM_CHANNEL_2
#define MOTOR_LEFT_PWM_PIN            GPIO_PIN_6
#define MOTOR_LEFT_PWM_PORT           GPIOA
#define MOTOR_RIGHT_PWM_PIN           GPIO_PIN_7
#define MOTOR_RIGHT_PWM_PORT          GPIOA

/*
 * Board photo silk indicates separate forward/backward logic inputs per motor:
 *   M1_F -> PA0, M1_B -> PA1
 *   M2_F -> PA15, M2_B -> PB3
 * TIM3 CH1/CH2 remain the speed PWM sources.
 *
 * Current firmware maps:
 *   left motor  -> M1
 *   right motor -> M2
 * Swap these pairs if the chassis sides are reversed mechanically.
 */
#define MOTOR_DIRECTION_GPIO_ENABLE   1u

#define MOTOR_LEFT_FWD_PIN            GPIO_PIN_0
#define MOTOR_LEFT_FWD_PORT           GPIOA
#define MOTOR_LEFT_REV_PIN            GPIO_PIN_1
#define MOTOR_LEFT_REV_PORT           GPIOA

#define MOTOR_RIGHT_FWD_PIN           GPIO_PIN_15
#define MOTOR_RIGHT_FWD_PORT          GPIOA
#define MOTOR_RIGHT_REV_PIN           GPIO_PIN_3
#define MOTOR_RIGHT_REV_PORT          GPIOB

#define MOTOR_PWM_ARR                 999U
#define MOTOR_PWM_MAX_DUTY            255U

/*
 * Optional low-speed bring-up routine.
 * Set MOTOR_SELF_TEST_ENABLE to 1 for a one-time startup sequence:
 *   left forward -> left reverse -> right forward -> right reverse.
 * Keep duty low until the tracks are confirmed safe on the bench.
 */
#define MOTOR_SELF_TEST_ENABLE        0u
#define MOTOR_SELF_TEST_DUTY          96u
#define MOTOR_SELF_TEST_STEP_MS       1200u
#define MOTOR_SELF_TEST_PAUSE_MS      600u

/* Exported types ------------------------------------------------------------*/

/* Exported constants --------------------------------------------------------*/

/* Exported macro ------------------------------------------------------------*/

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
