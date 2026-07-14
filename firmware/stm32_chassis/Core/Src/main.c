/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body for STM32F407VGTx chassis controller
  ******************************************************************************
  * @attention
  *
  * Rock64 Ranger - STM32 Chassis Controller
  * Motor control and sensor interfacing for tank robot
  *
  ******************************************************************************
  */

#include "main.h"
#include "stm32f4xx_hal.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* Private variables ---------------------------------------------------------*/
UART_HandleTypeDef huart2;  // UART for ROS2 bridge communication
I2C_HandleTypeDef hi2c1;    // I2C for MPU6050 IMU
TIM_HandleTypeDef htim3;    // TIM3 PWM outputs for left/right motor speed

/* Motor control state */
typedef struct {
  int16_t left_motor_speed;
  int16_t right_motor_speed;
  uint32_t last_command_time;
  uint8_t emergency_stop;
  uint8_t heartbeat_enabled;
} MotorState_t;

MotorState_t motor_state = {0, 0, 0, 0, 1};

/* Safety constants */
#define COMMAND_TIMEOUT_MS  200    // Timeout for motor commands
#define HEARTBEAT_INTERVAL_MS 100   // Heartbeat send interval
#define UART_BUFFER_SIZE 64

/* UART receive buffer */
volatile uint8_t uart_rx_buffer[UART_BUFFER_SIZE];
volatile uint16_t uart_rx_index = 0;
volatile uint8_t uart_command_ready = 0;

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_I2C1_Init(void);
static void MX_TIM3_Init(void);
static void update_motor_pwm(void);
void motor_safety_check(void);
void send_heartbeat(void);
void process_uart_command(char *command);
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart);

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* Configure the system clock */
  SystemClock_Config();

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART2_UART_Init();
  MX_I2C1_Init();
  MX_TIM3_Init();

  if (HAL_TIM_PWM_Start(&htim3, MOTOR_LEFT_PWM_CHANNEL) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Start(&htim3, MOTOR_RIGHT_PWM_CHANNEL) != HAL_OK)
  {
    Error_Handler();
  }

  /* Initialize motor state */
  motor_state.left_motor_speed = 0;
  motor_state.right_motor_speed = 0;
  motor_state.last_command_time = HAL_GetTick();
  motor_state.emergency_stop = 0;
  motor_state.heartbeat_enabled = 1;
  update_motor_pwm();

  /* Start UART receive in interrupt mode */
  HAL_UART_Receive_IT(&huart2, (uint8_t*)&uart_rx_buffer[uart_rx_index], 1);

  /* Main application loop */
  while (1)
  {
    /* Process UART commands if ready */
    if (uart_command_ready)
    {
      uart_command_ready = 0;
      process_uart_command((char*)uart_rx_buffer);
      uart_rx_index = 0;
      HAL_UART_Receive_IT(&huart2, (uint8_t*)&uart_rx_buffer[uart_rx_index], 1);
    }

    /* Motor safety watchdog - stop motors if no commands received */
    motor_safety_check();

    /* Send heartbeat to ROS2 bridge */
    send_heartbeat();

    /* Small delay to prevent CPU hogging */
    HAL_Delay(10);
  }
}

/**
  * @brief Motor safety watchdog
  * @note Stops motors if no commands received within timeout
  */
void motor_safety_check(void)
{
  uint32_t current_time = HAL_GetTick();

  if ((current_time - motor_state.last_command_time) > COMMAND_TIMEOUT_MS)
  {
    /* Command timeout - stop motors */
    if (motor_state.left_motor_speed != 0 || motor_state.right_motor_speed != 0)
    {
      motor_state.left_motor_speed = 0;
      motor_state.right_motor_speed = 0;
      motor_state.emergency_stop = 1;
      update_motor_pwm();

      /* TODO: Send emergency stop notification via UART */
    }
  }
}

/**
  * @brief Send heartbeat to ROS2 bridge
  */
void send_heartbeat(void)
{
  static uint32_t last_heartbeat = 0;
  uint32_t current_time = HAL_GetTick();

  if ((current_time - last_heartbeat) >= HEARTBEAT_INTERVAL_MS)
  {
    last_heartbeat = current_time;

    /* Send heartbeat packet via UART */
    const char *heartbeat_msg = "HB\n";
    HAL_UART_Transmit(&huart2, (uint8_t*)heartbeat_msg, strlen(heartbeat_msg), 100);
  }
}

/**
  * @brief Process UART command from Rock64
  * @param command: Null-terminated command string
  */
void process_uart_command(char *command)
{
  if (strncmp(command, "PING", 4) == 0)
  {
    const char *hb_msg = "HB\n";
    HAL_UART_Transmit(&huart2, (uint8_t*)hb_msg, strlen(hb_msg), 100);
    return;
  }

  /* Parse one or more frames in a single line: <id,dir,speed><id,dir,speed> */
  char *cursor = command;
  uint8_t parsed_any = 0;
  while ((cursor = strchr(cursor, '<')) != NULL)
  {
    int motor_id = 0;
    int direction = 0;
    int speed = 0;

    if (sscanf(cursor, "<%d,%d,%d>", &motor_id, &direction, &speed) == 3)
    {
      if (speed < 0)
      {
        speed = 0;
      }
      if (speed > MOTOR_PWM_MAX_DUTY)
      {
        speed = MOTOR_PWM_MAX_DUTY;
      }

      if (motor_id == 0)
      {
        motor_state.left_motor_speed = (direction ? speed : -speed);
      }
      else if (motor_id == 1)
      {
        motor_state.right_motor_speed = (direction ? speed : -speed);
      }

      parsed_any = 1;
    }

    cursor++;
  }

  if (parsed_any)
  {
    update_motor_pwm();
    motor_state.last_command_time = HAL_GetTick();
    motor_state.emergency_stop = 0;

    const char *ack_msg = "ACK\n";
    HAL_UART_Transmit(&huart2, (uint8_t*)ack_msg, strlen(ack_msg), 100);
  }
}

/**
  * @brief Convert signed motor speeds into PWM duty on TIM3 CH1/CH2.
  */
static void update_motor_pwm(void)
{
  uint16_t left_abs = (motor_state.left_motor_speed < 0) ?
    (uint16_t)(-motor_state.left_motor_speed) : (uint16_t)motor_state.left_motor_speed;
  uint16_t right_abs = (motor_state.right_motor_speed < 0) ?
    (uint16_t)(-motor_state.right_motor_speed) : (uint16_t)motor_state.right_motor_speed;

  if (left_abs > MOTOR_PWM_MAX_DUTY)
  {
    left_abs = MOTOR_PWM_MAX_DUTY;
  }
  if (right_abs > MOTOR_PWM_MAX_DUTY)
  {
    right_abs = MOTOR_PWM_MAX_DUTY;
  }

  __HAL_TIM_SET_COMPARE(&htim3, MOTOR_LEFT_PWM_CHANNEL,
    (left_abs * MOTOR_PWM_ARR) / MOTOR_PWM_MAX_DUTY);
  __HAL_TIM_SET_COMPARE(&htim3, MOTOR_RIGHT_PWM_CHANNEL,
    (right_abs * MOTOR_PWM_ARR) / MOTOR_PWM_MAX_DUTY);
}

/**
  * @brief UART receive complete callback
  */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART2)
  {
    /* Check for end of command (newline) */
    if (uart_rx_buffer[uart_rx_index] == '\n')
    {
      uart_rx_buffer[uart_rx_index] = '\0';  /* Null-terminate */
      uart_command_ready = 1;
    }
    else
    {
      uart_rx_index++;
      if (uart_rx_index < UART_BUFFER_SIZE - 1)
      {
        /* Continue receiving */
        HAL_UART_Receive_IT(&huart2, (uint8_t*)&uart_rx_buffer[uart_rx_index], 1);
      }
      else
      {
        /* Buffer overflow, reset */
        uart_rx_index = 0;
        HAL_UART_Receive_IT(&huart2, (uint8_t*)&uart_rx_buffer[uart_rx_index], 1);
      }
    }
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

  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /* RM0090 PLL profile for 168MHz SYSCLK from 8MHz HSE. */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 8;
  RCC_OscInitStruct.PLL.PLLN = 336;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 7;

  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    /* Fallback if external clock is unavailable. */
    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSEState = RCC_HSE_OFF;
    RCC_OscInitStruct.HSIState = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
    RCC_OscInitStruct.PLL.PLLM = 16;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
      Error_Handler();
    }
  }

  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                                RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;
  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief USART2 Initialization
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{
  huart2.Instance = ROCK64_UART_INSTANCE;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief I2C1 Initialization
  * @retval None
  */
static void MX_I2C1_Init(void)
{
  hi2c1.Instance = MPU6050_I2C_INSTANCE;
  hi2c1.Init.ClockSpeed = 100000;
  hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief TIM3 Initialization for motor PWM generation.
  * @retval None
  */
static void MX_TIM3_Init(void)
{
  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  htim3.Instance = MOTOR_PWM_TIMER;
  htim3.Init.Prescaler = 83;
  htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim3.Init.Period = MOTOR_PWM_ARR;
  htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
  if (HAL_TIM_Base_Init(&htim3) != HAL_OK)
  {
    Error_Handler();
  }

  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim3, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }

  if (HAL_TIM_PWM_Init(&htim3) != HAL_OK)
  {
    Error_Handler();
  }

  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }

  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim3, &sConfigOC, MOTOR_LEFT_PWM_CHANNEL) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim3, &sConfigOC, MOTOR_RIGHT_PWM_CHANNEL) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief GPIO Initialization
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  /* GPIO setup for USART2/I2C1/TIM3 PWM is in HAL MSP callbacks. */
}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
    /* Toggle error LED if available */
    HAL_Delay(500);
  }
}

/**
  * @brief USART2 IRQ Handler
  * @retval None
  */
void USART2_IRQHandler(void)
{
  HAL_UART_IRQHandler(&huart2);
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
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
}
#endif /* USE_FULL_ASSERT */
