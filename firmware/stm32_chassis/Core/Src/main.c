/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "cmsis_os.h"
#include "adc.h"
#include "crc.h"
#include "dma.h"
#include "i2c.h"
#include "spi.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"
#include "usb_device.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "uart_binary_protocol_integration_packed.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
extern UART_HandleTypeDef huart1;
extern UART_HandleTypeDef huart6;

static uint32_t protocol_task_stack[256];
static StaticTask_t protocol_task_control_block;
static const osThreadAttr_t protocol_task_attributes = {
  .name = "protocol_task",
  .cb_mem = &protocol_task_control_block,
  .cb_size = sizeof(protocol_task_control_block),
  .stack_mem = &protocol_task_stack[0],
  .stack_size = sizeof(protocol_task_stack),
  .priority = (osPriority_t)osPriorityNormal,
};
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
void MX_FREERTOS_Init(void);

/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* SystemInit deliberately masks interrupts while it clears inherited NVIC
   * state.  The motor image does not need the legacy USB-CDC device, and the
   * USB stack performs short HAL_Delay() calls during enumeration setup.
   * Enable the clean timebase before the remaining peripheral bring-up. */
  __enable_irq();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* The Rock64 link is the Hiwonder WCH USB-UART bridge on product UART1:
   * USART1 PA9/PA10 at 1 Mbaud. USART3 is the factory pair; USART2 is BLE. */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_USART1_UART_Init();
  MX_SPI2_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM5_Init();
  MX_TIM7_Init();
  MX_TIM9_Init();
  MX_TIM10_Init();
  MX_TIM11_Init();
  MX_I2C2_Init();
  MX_UART5_Init();
  MX_USART2_UART_Init();
  MX_USART3_UART_Init();
  MX_USART6_UART_Init();
  MX_TIM3_Init();
  MX_TIM4_Init();
  MX_TIM12_Init();
  MX_TIM13_Init();
  MX_ADC1_Init();
  MX_CRC_Init();
  /* The Rock64 motor link is the WCH UART1 connector.  Do not initialize the
   * legacy OTG-HS CDC stack here: on this controller it is not wired into the
   * host path and its startup delay can deadlock while no USB device exists. */

  /* The custom motor protocol owns its 100 Hz update loop.  TIM7 is a
   * legacy speed-measurement timer and has no registered HAL callback in
   * this image.  NRST is not wired on the bench board, so an SWD-launched
   * image can inherit a stale TIM7 enable/pending bit from the previous
   * image; leave the legacy interrupt disabled before global IRQ enable. */
  HAL_NVIC_DisableIRQ(TIM7_IRQn);
  __HAL_TIM_DISABLE_IT(&htim7, TIM_IT_UPDATE);
  __HAL_TIM_CLEAR_IT(&htim7, TIM_IT_UPDATE);

  osKernelInitialize();
  MX_FREERTOS_Init();
  if (osThreadNew(binary_protocol_task, NULL, &protocol_task_attributes) == NULL) {
    Error_Handler();
  }
  osKernelStart();

  /* The scheduler owns the application after osKernelStart(). */
  for (;;) {
  }
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  /* Use the STM32F407 internal HSI clock.  The Rock64 motor-controller board
   * does not reliably provide the external HSE oscillator at boot; a failed
   * HSE startup traps here before USART1 can service the Rock64 link.  HSI
   * 16 MHz -> 168 MHz SYSCLK keeps APB1=42 MHz and APB2=84 MHz, so the UART
   * baud-rate divisors, motor timers, and FreeRTOS timebase remain stable. */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 16;
  RCC_OscInitStruct.PLL.PLLN = 336;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 7;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    Error_Handler();
  }

  /** Enables the Clock Security System
  */
  HAL_RCC_EnableCSS();
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  Period elapsed callback in non blocking mode
  * @note   TIM14 is handled by the custom HAL timebase implementation in
  * stm32f4xx_hal_timebase_tim.c, which calls HAL_IncTick().
  * @param  htim : TIM handle
  * @retval None
  */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  /* USER CODE BEGIN Callback 0 */

  /* USER CODE END Callback 0 */
  /* TIM14 is the registered HAL timebase callback. It is dispatched by
   * TIM8_TRG_COM_TIM14_IRQHandler(), not from this legacy callback. */
  /* PA8 is a plain GPIO in this production image. TIM12 supplies the
   * half-period callbacks used to generate the buzzer square wave. */
  if (htim == &htim12) {
    HAL_GPIO_WritePin(BUZZER_GPIO_Port, BUZZER_Pin, GPIO_PIN_SET);
  }
  /* USER CODE BEGIN Callback 1 */

  /* USER CODE END Callback 1 */
}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
