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

#define MOTOR_PWM_ARR                 999U
#define MOTOR_PWM_MAX_DUTY            255U

/* Exported types ------------------------------------------------------------*/

/* Exported constants --------------------------------------------------------*/

/* Exported macro ------------------------------------------------------------*/

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
