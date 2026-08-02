/**
 * @file motor_control.c
 * @brief Motor control wrapper implementation using Hiwonder's existing system
 * 
 * This implementation uses Hiwonder's encoder_motor library which already
 * includes PID control, encoder reading, and PWM generation. We simply provide
 * the ROS2-compatible interface layer.
 */

#include "motor_control.h"
#include "encoder_motor.h"
#include "tim.h"
#include <string.h>

// ============================================================================
// GLOBAL STATE
// ============================================================================

MotorState_t motor_states[MOTOR_COUNT];

// External Hiwonder motor array (from motor_porting.c)
extern EncoderMotorObjectTypeDef *motors[4];

// Encoder timer handles for reading encoder counts
extern TIM_HandleTypeDef htim2;  // Motor 2 encoder
extern TIM_HandleTypeDef htim3;  // Motor 4 encoder  
extern TIM_HandleTypeDef htim4;  // Motor 3 encoder
extern TIM_HandleTypeDef htim5;  // Motor 1 encoder

void motors_init(void);

// ============================================================================
// INITIALIZATION
// ============================================================================

void MotorControl_Init(void) {
    static bool initialized = false;

    if (initialized) {
        return;
    }

    motors_init();

    // Clear motor state
    memset(motor_states, 0, sizeof(motor_states));
    
    // Initialize all motors as enabled
    for (int i = 0; i < MOTOR_COUNT; i++) {
        motor_states[i].enabled = true;
    }

    initialized = true;
}

// ============================================================================
// TARGET VELOCITY SETTING
// ============================================================================

void MotorControl_SetTargetRPS(uint8_t motor_id, float target_rps) {
    if (motor_id >= MOTOR_COUNT) {
        return;  // Invalid motor ID
    }
    
    if (!motor_states[motor_id].enabled) {
        return;  // Motor disabled
    }
    
    // Store target for telemetry
    motor_states[motor_id].target_rps = target_rps;
    
    // Use Hiwonder's existing PID target setting
    // This directly sets the set_point for their PID controller
    if (motors[motor_id] != NULL) {
        encoder_motor_set_speed(motors[motor_id], target_rps);
    }
}

// ============================================================================
// CURRENT STATE READING
// ============================================================================

float MotorControl_GetCurrentRPS(uint8_t motor_id) {
    if (motor_id >= MOTOR_COUNT) {
        return 0.0f;
    }
    
    // Return cached RPS from our state (updated in MotorControl_Update)
    return motor_states[motor_id].current_rps;
}

int32_t MotorControl_GetEncoderCount(uint8_t motor_id) {
    if (motor_id >= MOTOR_COUNT) {
        return 0;
    }
    
    // Read encoder count from timer
    TIM_HandleTypeDef *encoder_timer = NULL;
    
    switch (motor_id) {
        case 0: encoder_timer = &htim5; break;  // Motor 1
        case 1: encoder_timer = &htim2; break;  // Motor 2
        case 2: encoder_timer = &htim4; break;  // Motor 3
        case 3: encoder_timer = &htim3; break;  // Motor 4
        default: return 0;
    }
    
    if (encoder_timer != NULL) {
        return __HAL_TIM_GET_COUNTER(encoder_timer);
    }
    
    return 0;
}

// ============================================================================
// CONTROL LOOP UPDATE
// ============================================================================

void MotorControl_Update(float period) {
    for (int i = 0; i < MOTOR_COUNT; i++) {
        if (!motor_states[i].enabled || motors[i] == NULL) {
            continue;
        }
        
        // Read current encoder count
        int32_t current_encoder = MotorControl_GetEncoderCount(i);
        motor_states[i].encoder_count = current_encoder;
        
        // Update encoder reading and calculate RPS using Hiwonder's function
        // This handles overflow, filtering, and RPS calculation
        encoder_update(motors[i], period, current_encoder);
        
        // Store current RPS for telemetry
        motor_states[i].current_rps = motors[i]->rps;
        
        // Run PID control using Hiwonder's existing controller
        // This calculates PWM and calls the set_pulse function automatically
        encoder_motor_control(motors[i], period);
    }
}

// ============================================================================
// EMERGENCY STOP
// ============================================================================

void MotorControl_EmergencyStop(void) {
    for (int i = 0; i < MOTOR_COUNT; i++) {
        motor_states[i].target_rps = 0.0f;

        if (motors[i] == NULL) {
            continue;
        }

        motors[i]->pid_controller.set_point = 0.0f;
        motors[i]->pid_controller.previous_0_err = 0.0f;
        motors[i]->pid_controller.previous_1_err = 0.0f;
        motors[i]->pid_controller.output = 0.0f;
        motors[i]->current_pulse = 0;
        motors[i]->set_pulse(motors[i], 0);
    }
}

// ============================================================================
// ENABLE/DISABLE CONTROL
// ============================================================================

void MotorControl_SetEnable(uint8_t motor_id, bool enabled) {
    if (motor_id >= MOTOR_COUNT) {
        return;
    }
    
    motor_states[motor_id].enabled = enabled;
    
    if (!enabled) {
        // If disabling, set target to 0
        MotorControl_SetTargetRPS(motor_id, 0.0f);
    }
}

bool MotorControl_GetEnable(uint8_t motor_id) {
    if (motor_id >= MOTOR_COUNT) {
        return false;
    }
    
    return motor_states[motor_id].enabled;
}
