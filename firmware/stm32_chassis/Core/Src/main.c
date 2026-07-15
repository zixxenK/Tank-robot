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
#include "microros_app.h"
#include "protocol_def.h"
#include "protocol_gateway.h"
#include "stm32f4xx_hal.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* Private variables ---------------------------------------------------------*/
UART_HandleTypeDef huart2;  // UART for ROS2 bridge communication
I2C_HandleTypeDef hi2c1;    // I2C for MPU6050 IMU
TIM_HandleTypeDef htim3;    // TIM3 PWM outputs for left/right motor speed
extern DMA_HandleTypeDef hdma_usart2_rx;

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
static void run_motor_self_test(void);
static void send_self_test_status(uint8_t status_code);
static void execute_self_test_with_ack(void);
static void apply_binary_speed_pair(int16_t left_speed, int16_t right_speed);
static void binary_command_handler(uint8_t function_code,
                                   const uint8_t *payload,
                                   uint8_t payload_len);
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

#if MOTOR_SELF_TEST_ENABLE
  run_motor_self_test();
#endif

  protocol_gateway_reset();
  protocol_gateway_set_handler(binary_command_handler);

  /* micro-ROS control task: support -> node -> subscriber -> executor */
  StartDefaultTask(NULL);

  while (1)
  {
    /* StartDefaultTask is expected to run forever. */
  }
}

static void run_motor_self_test(void)
{
  const int16_t test_duty = (int16_t)MOTOR_SELF_TEST_DUTY;

  apply_binary_speed_pair(0, 0);
  HAL_Delay(MOTOR_SELF_TEST_PAUSE_MS);

  apply_binary_speed_pair(test_duty, 0);
  HAL_Delay(MOTOR_SELF_TEST_STEP_MS);
  apply_binary_speed_pair(0, 0);
  HAL_Delay(MOTOR_SELF_TEST_PAUSE_MS);

  apply_binary_speed_pair(-test_duty, 0);
  HAL_Delay(MOTOR_SELF_TEST_STEP_MS);
  apply_binary_speed_pair(0, 0);
  HAL_Delay(MOTOR_SELF_TEST_PAUSE_MS);

  apply_binary_speed_pair(0, test_duty);
  HAL_Delay(MOTOR_SELF_TEST_STEP_MS);
  apply_binary_speed_pair(0, 0);
  HAL_Delay(MOTOR_SELF_TEST_PAUSE_MS);

  apply_binary_speed_pair(0, -test_duty);
  HAL_Delay(MOTOR_SELF_TEST_STEP_MS);
  apply_binary_speed_pair(0, 0);
  HAL_Delay(MOTOR_SELF_TEST_PAUSE_MS);
}

static void send_self_test_status(uint8_t status_code)
{
  uint8_t payload[1u] = {status_code};
  uint8_t frame[9u];
  size_t frame_len = protocol_build_frame(PROTO_FUNC_SELF_TEST,
                                          payload,
                                          1u,
                                          frame,
                                          sizeof(frame));
  if (frame_len > 0u)
  {
    HAL_UART_Transmit(&huart2, frame, (uint16_t)frame_len, 100u);
  }
}

static void execute_self_test_with_ack(void)
{
  apply_binary_speed_pair(0, 0);
  send_self_test_status(PROTO_TEST_STARTED);
  run_motor_self_test();
  apply_binary_speed_pair(0, 0);
  send_self_test_status(PROTO_TEST_FINISHED);
  motor_state.last_command_time = HAL_GetTick();
}

static void apply_binary_speed_pair(int16_t left_speed, int16_t right_speed)
{
  if (left_speed > (int16_t)MOTOR_PWM_MAX_DUTY)
  {
    left_speed = (int16_t)MOTOR_PWM_MAX_DUTY;
  }
  if (left_speed < -(int16_t)MOTOR_PWM_MAX_DUTY)
  {
    left_speed = -(int16_t)MOTOR_PWM_MAX_DUTY;
  }

  if (right_speed > (int16_t)MOTOR_PWM_MAX_DUTY)
  {
    right_speed = (int16_t)MOTOR_PWM_MAX_DUTY;
  }
  if (right_speed < -(int16_t)MOTOR_PWM_MAX_DUTY)
  {
    right_speed = -(int16_t)MOTOR_PWM_MAX_DUTY;
  }

  motor_state.left_motor_speed = left_speed;
  motor_state.right_motor_speed = right_speed;
  motor_state.last_command_time = HAL_GetTick();
  motor_state.emergency_stop = 0;
  update_motor_pwm();
}

static void binary_command_handler(uint8_t function_code,
                                   const uint8_t *payload,
                                   uint8_t payload_len)
{
  if (function_code == PROTO_FUNC_LED && payload_len == 7u)
  {
    motor_state.last_command_time = HAL_GetTick();
    return;
  }

  if (function_code == PROTO_FUNC_BUZZER && payload_len == 8u)
  {
    motor_state.last_command_time = HAL_GetTick();
    return;
  }

  if ((function_code == PROTO_FUNC_PWM_SERVO ||
       function_code == PROTO_FUNC_BUS_SERVO) &&
      payload_len >= 1u)
  {
    motor_state.last_command_time = HAL_GetTick();
    return;
  }

  if (function_code == PROTO_FUNC_MOTOR && payload_len >= 2u)
  {
    uint8_t subcmd = payload[0];
    uint8_t count = payload[1];
    int16_t left_speed = motor_state.left_motor_speed;
    int16_t right_speed = motor_state.right_motor_speed;
    uint8_t max_entries = (uint8_t)((payload_len - 2u) / 5u);

    if (subcmd == PROTO_MOTOR_SUBCMD_SET_SPEED)
    {
      if (count > max_entries)
      {
        count = max_entries;
      }

      for (uint8_t i = 0u; i < count; ++i)
      {
        uint16_t base = (uint16_t)(2u + (i * 5u));
        uint8_t motor_id = payload[base];
        float motor_rps = 0.0f;
        float clamped_rps;

        memcpy(&motor_rps, &payload[base + 1u], sizeof(float));
        clamped_rps = motor_rps;
        if (clamped_rps > 1.0f)
        {
          clamped_rps = 1.0f;
        }
        if (clamped_rps < -1.0f)
        {
          clamped_rps = -1.0f;
        }

        if (motor_id == 0u)
        {
          left_speed = (int16_t)(clamped_rps * (float)MOTOR_PWM_MAX_DUTY);
        }
        else if (motor_id == 1u)
        {
          right_speed = (int16_t)(clamped_rps * (float)MOTOR_PWM_MAX_DUTY);
        }
      }

      apply_binary_speed_pair(left_speed, right_speed);
    }
    return;
  }

  if (function_code == PROTO_FUNC_MOTOR_SET_BOTH && payload_len == 4u)
  {
    int16_t left_speed = (int16_t)((uint16_t)payload[0] |
      ((uint16_t)payload[1] << 8));
    int16_t right_speed = (int16_t)((uint16_t)payload[2] |
      ((uint16_t)payload[3] << 8));
    apply_binary_speed_pair(left_speed, right_speed);
    return;
  }

  if (function_code == PROTO_FUNC_MOTOR_SET_SINGLE && payload_len == 4u)
  {
    uint8_t motor_id = payload[0];
    uint8_t direction = payload[1] != 0u ? 1u : 0u;
    uint16_t speed_u16 = (uint16_t)payload[2] | ((uint16_t)payload[3] << 8);
    int16_t signed_speed = (int16_t)speed_u16;
    if (direction == 0u)
    {
      signed_speed = (int16_t)(-signed_speed);
    }

    if (motor_id == 0u)
    {
      apply_binary_speed_pair(signed_speed, motor_state.right_motor_speed);
    }
    else if (motor_id == 1u)
    {
      apply_binary_speed_pair(motor_state.left_motor_speed, signed_speed);
    }
    return;
  }

  if (function_code == PROTO_FUNC_EMERGENCY_STOP)
  {
    motor_state.left_motor_speed = 0;
    motor_state.right_motor_speed = 0;
    motor_state.emergency_stop = 1;
    update_motor_pwm();
    return;
  }

  if (function_code == PROTO_FUNC_SELF_TEST && payload_len == 0u)
  {
    execute_self_test_with_ack();
    return;
  }

  if (function_code == PROTO_FUNC_HEARTBEAT)
  {
    motor_state.last_command_time = HAL_GetTick();
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

    uint8_t frame[8u];
    size_t frame_len = protocol_build_frame(PROTO_FUNC_HEARTBEAT,
                                            NULL,
                                            0u,
                                            frame,
                                            sizeof(frame));
    if (frame_len > 0u)
    {
      HAL_UART_Transmit(&huart2, frame, (uint16_t)frame_len, 100);
    }
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

  if (strncmp(command, "SELFTEST", 8) == 0)
  {
    execute_self_test_with_ack();
    const char *ack_msg = "SELFTEST_OK\n";
    HAL_UART_Transmit(&huart2, (uint8_t*)ack_msg, strlen(ack_msg), 100);
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

#if MOTOR_DIRECTION_GPIO_ENABLE
  if (motor_state.left_motor_speed > 0)
  {
    HAL_GPIO_WritePin(MOTOR_LEFT_FWD_PORT, MOTOR_LEFT_FWD_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(MOTOR_LEFT_REV_PORT, MOTOR_LEFT_REV_PIN, GPIO_PIN_RESET);
  }
  else if (motor_state.left_motor_speed < 0)
  {
    HAL_GPIO_WritePin(MOTOR_LEFT_FWD_PORT, MOTOR_LEFT_FWD_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(MOTOR_LEFT_REV_PORT, MOTOR_LEFT_REV_PIN, GPIO_PIN_SET);
  }
  else
  {
    HAL_GPIO_WritePin(MOTOR_LEFT_FWD_PORT, MOTOR_LEFT_FWD_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(MOTOR_LEFT_REV_PORT, MOTOR_LEFT_REV_PIN, GPIO_PIN_RESET);
  }

  if (motor_state.right_motor_speed > 0)
  {
    HAL_GPIO_WritePin(MOTOR_RIGHT_FWD_PORT, MOTOR_RIGHT_FWD_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(MOTOR_RIGHT_REV_PORT, MOTOR_RIGHT_REV_PIN, GPIO_PIN_RESET);
  }
  else if (motor_state.right_motor_speed < 0)
  {
    HAL_GPIO_WritePin(MOTOR_RIGHT_FWD_PORT, MOTOR_RIGHT_FWD_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(MOTOR_RIGHT_REV_PORT, MOTOR_RIGHT_REV_PIN, GPIO_PIN_SET);
  }
  else
  {
    HAL_GPIO_WritePin(MOTOR_RIGHT_FWD_PORT, MOTOR_RIGHT_FWD_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(MOTOR_RIGHT_REV_PORT, MOTOR_RIGHT_REV_PIN, GPIO_PIN_RESET);
  }
#endif
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
#if MOTOR_DIRECTION_GPIO_ENABLE
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  GPIO_InitStruct.Pin = MOTOR_LEFT_FWD_PIN | MOTOR_LEFT_REV_PIN |
                        MOTOR_RIGHT_FWD_PIN;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  GPIO_InitStruct.Pin = MOTOR_RIGHT_REV_PIN;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  HAL_GPIO_WritePin(MOTOR_LEFT_FWD_PORT, MOTOR_LEFT_FWD_PIN, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(MOTOR_LEFT_REV_PORT, MOTOR_LEFT_REV_PIN, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(MOTOR_RIGHT_FWD_PORT, MOTOR_RIGHT_FWD_PIN, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(MOTOR_RIGHT_REV_PORT, MOTOR_RIGHT_REV_PIN, GPIO_PIN_RESET);
#endif
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

/**
  * @brief DMA1 Stream5 IRQ Handler for USART2 RX DMA
  * @retval None
  */
void DMA1_Stream5_IRQHandler(void)
{
  HAL_DMA_IRQHandler(&hdma_usart2_rx);
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
