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

/* Private variables ---------------------------------------------------------*/
UART_HandleTypeDef huart2;  // UART for ROS2 bridge communication
I2C_HandleTypeDef hi2c1;    // I2C for MPU6050 IMU

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

  /* Initialize motor state */
  motor_state.left_motor_speed = 0;
  motor_state.right_motor_speed = 0;
  motor_state.last_command_time = HAL_GetTick();
  motor_state.emergency_stop = 0;
  motor_state.heartbeat_enabled = 1;

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
  /* Parse command format: <motor_id,direction,speed> */
  if (command[0] == '<' && command[1] >= '0' && command[1] <= '1')
  {
    uint8_t motor_id = command[1] - '0';
    uint8_t direction = 0;
    uint8_t speed = 0;

    /* Parse direction and speed */
    char *comma1 = strchr(command, ',');
    char *comma2 = NULL;

    if (comma1)
    {
      direction = atoi(comma1 + 1);
      comma2 = strchr(comma1 + 1, ',');
    }

    if (comma2)
    {
      speed = atoi(comma2 + 1);
    }

    /* Update motor state */
    if (motor_id == 0)
    {
      motor_state.left_motor_speed = (direction ? speed : -speed);
    }
    else
    {
      motor_state.right_motor_speed = (direction ? speed : -speed);
    }

    /* Update last command time */
    motor_state.last_command_time = HAL_GetTick();

    /* Clear emergency stop if we're receiving commands */
    if (motor_state.emergency_stop)
    {
      motor_state.emergency_stop = 0;
    }

    /* Send acknowledgment */
    const char *ack_msg = "ACK\n";
    HAL_UART_Transmit(&huart2, (uint8_t*)ack_msg, strlen(ack_msg), 100);
  }
  else if (strncmp(command, "PING", 4) == 0)
  {
    /* Respond to heartbeat ping */
    const char *hb_msg = "HB\n";
    HAL_UART_Transmit(&huart2, (uint8_t*)hb_msg, strlen(hb_msg), 100);
  }
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
  /* TODO: Configure system clock for 168MHz operation */
  /* This is a placeholder - actual configuration depends on hardware setup */
}

/**
  * @brief USART2 Initialization
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{
  huart2.Instance = USART2;
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

  /* Enable UART interrupt */
  HAL_NVIC_SetPriority(USART2_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(USART2_IRQn);
}

/**
  * @brief I2C1 Initialization
  * @retval None
  */
static void MX_I2C1_Init(void)
{
  hi2c1.Instance = I2C1;
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
  * @brief GPIO Initialization
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOD_CLK_ENABLE();

  /* TODO: Configure motor control GPIO pins */
  /* TODO: Configure LED pins for status indication */
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
