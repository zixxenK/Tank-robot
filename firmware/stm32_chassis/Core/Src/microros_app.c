#include "microros_app.h"

#include <math.h>
#include <string.h>

#include "cubemx_transport.h"

#include "geometry_msgs/msg/twist.h"
#include "rcl/rcl.h"
#include "rclc/executor.h"
#include "rclc/rclc.h"
#include "rmw_microros/rmw_microros.h"

#define TRACK_WIDTH_M             0.194f
#define MAX_LINEAR_SPEED_MPS      0.60f
#define MAX_ANGULAR_SPEED_RADPS   1.80f
#define MOTOR_PWM_MAX_DUTY        255U
#define MOTOR_PWM_ARR             999U
#define COMMAND_TIMEOUT_MS        300U
#define SPIN_PERIOD_MS             10U

extern UART_HandleTypeDef huart2;
extern TIM_HandleTypeDef htim3;

typedef struct
{
  float target_linear;
  float target_angular;
  uint32_t last_command_tick;
} MotorCommandState_t;

static MotorCommandState_t s_motor_state = {
  .target_linear = 0.0f,
  .target_angular = 0.0f,
  .last_command_tick = 0U,
};

static rcl_subscription_t s_cmd_vel_sub;
static geometry_msgs__msg__Twist s_cmd_vel_msg;
static rcl_node_t s_node;
static rclc_support_t s_support;
static rclc_executor_t s_executor;
static rcl_allocator_t s_allocator;

static void update_pwm_from_signed_speed(float left_speed, float right_speed)
{
  float left_abs = fabsf(left_speed);
  float right_abs = fabsf(right_speed);

  if (left_abs > 1.0f)
  {
    left_abs = 1.0f;
  }
  if (right_abs > 1.0f)
  {
    right_abs = 1.0f;
  }

  uint16_t left_pwm = (uint16_t)(left_abs * MOTOR_PWM_ARR);
  uint16_t right_pwm = (uint16_t)(right_abs * MOTOR_PWM_ARR);

#if MOTOR_DIRECTION_GPIO_ENABLE
  if (left_speed > 0.0f)
  {
    HAL_GPIO_WritePin(MOTOR_LEFT_FWD_PORT, MOTOR_LEFT_FWD_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(MOTOR_LEFT_REV_PORT, MOTOR_LEFT_REV_PIN, GPIO_PIN_RESET);
  }
  else if (left_speed < 0.0f)
  {
    HAL_GPIO_WritePin(MOTOR_LEFT_FWD_PORT, MOTOR_LEFT_FWD_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(MOTOR_LEFT_REV_PORT, MOTOR_LEFT_REV_PIN, GPIO_PIN_SET);
  }
  else
  {
    HAL_GPIO_WritePin(MOTOR_LEFT_FWD_PORT, MOTOR_LEFT_FWD_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(MOTOR_LEFT_REV_PORT, MOTOR_LEFT_REV_PIN, GPIO_PIN_RESET);
  }

  if (right_speed > 0.0f)
  {
    HAL_GPIO_WritePin(MOTOR_RIGHT_FWD_PORT, MOTOR_RIGHT_FWD_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(MOTOR_RIGHT_REV_PORT, MOTOR_RIGHT_REV_PIN, GPIO_PIN_RESET);
  }
  else if (right_speed < 0.0f)
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

  __HAL_TIM_SET_COMPARE(&htim3, MOTOR_LEFT_PWM_CHANNEL, left_pwm);
  __HAL_TIM_SET_COMPARE(&htim3, MOTOR_RIGHT_PWM_CHANNEL, right_pwm);
}

static void stop_motors(void)
{
  update_pwm_from_signed_speed(0.0f, 0.0f);
}

static void apply_cmd_vel(const geometry_msgs__msg__Twist *msg)
{
  float linear = (float)msg->linear.x;
  float angular = (float)msg->angular.z;

  if (linear > MAX_LINEAR_SPEED_MPS)
  {
    linear = MAX_LINEAR_SPEED_MPS;
  }
  if (linear < -MAX_LINEAR_SPEED_MPS)
  {
    linear = -MAX_LINEAR_SPEED_MPS;
  }
  if (angular > MAX_ANGULAR_SPEED_RADPS)
  {
    angular = MAX_ANGULAR_SPEED_RADPS;
  }
  if (angular < -MAX_ANGULAR_SPEED_RADPS)
  {
    angular = -MAX_ANGULAR_SPEED_RADPS;
  }

  s_motor_state.target_linear = linear;
  s_motor_state.target_angular = angular;
  s_motor_state.last_command_tick = HAL_GetTick();

  float half_track = TRACK_WIDTH_M * 0.5f;
  float left_speed_mps = linear - (angular * half_track);
  float right_speed_mps = linear + (angular * half_track);

  float left_norm = left_speed_mps / MAX_LINEAR_SPEED_MPS;
  float right_norm = right_speed_mps / MAX_LINEAR_SPEED_MPS;

  if (left_norm > 1.0f)
  {
    left_norm = 1.0f;
  }
  if (left_norm < -1.0f)
  {
    left_norm = -1.0f;
  }
  if (right_norm > 1.0f)
  {
    right_norm = 1.0f;
  }
  if (right_norm < -1.0f)
  {
    right_norm = -1.0f;
  }

  update_pwm_from_signed_speed(left_norm, right_norm);
}

static void cmd_vel_callback(const void *msg_in)
{
  const geometry_msgs__msg__Twist *msg = (const geometry_msgs__msg__Twist *)msg_in;
  apply_cmd_vel(msg);
}

static void microros_setup(void)
{
  s_allocator = rcl_get_default_allocator();

  cubemx_transport_init(&huart2);
  rmw_uros_set_custom_transport(true,
                                NULL,
                                cubemx_transport_open,
                                cubemx_transport_close,
                                cubemx_transport_write,
                                cubemx_transport_read);

  while (!rmw_uros_ping_agent(500, 1))
  {
    HAL_Delay(200);
  }

  rcl_ret_t rc = rclc_support_init(&s_support, 0, NULL, &s_allocator);
  if (rc != RCL_RET_OK)
  {
    Error_Handler();
  }

  rc = rclc_node_init_default(&s_node, "stm32_motor_controller", "", &s_support);
  if (rc != RCL_RET_OK)
  {
    Error_Handler();
  }

  rc = rclc_subscription_init_default(
    &s_cmd_vel_sub,
    &s_node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist),
    "cmd_vel");
  if (rc != RCL_RET_OK)
  {
    Error_Handler();
  }

  rc = rclc_executor_init(&s_executor, &s_support.context, 1, &s_allocator);
  if (rc != RCL_RET_OK)
  {
    Error_Handler();
  }

  rc = rclc_executor_add_subscription(&s_executor,
                                      &s_cmd_vel_sub,
                                      &s_cmd_vel_msg,
                                      &cmd_vel_callback,
                                      ON_NEW_DATA);
  if (rc != RCL_RET_OK)
  {
    Error_Handler();
  }
}

static void motor_watchdog(void)
{
  uint32_t now = HAL_GetTick();
  if ((now - s_motor_state.last_command_tick) > COMMAND_TIMEOUT_MS)
  {
    stop_motors();
  }
}

void StartDefaultTask(void *argument)
{
  (void)argument;

  microros_setup();
  s_motor_state.last_command_tick = HAL_GetTick();

  for (;;)
  {
    rclc_executor_spin_some(&s_executor, RCL_MS_TO_NS(SPIN_PERIOD_MS));
    motor_watchdog();
    HAL_Delay(SPIN_PERIOD_MS);
  }
}