/**
 * @file status_integration.c
 * @brief Buzzer and LED status indicators integration
 * 
 * Provides emergency feedback, system status indication, and debugging
 * capabilities without requiring a monitor connection.
 */

#include "status_integration.h"
#include "buzzer.h"
#include "led.h"
#include "main.h"

// ============================================================================
// STATUS PERIPHERAL INSTANCES
// ============================================================================

static BuzzerObjectTypeDef emergency_buzzer;
static LEDObjectTypeDef status_led;

static bool status_initialized = false;

// ============================================================================
// BUZZER HARDWARE ABSTRACTION
// ============================================================================

static int buzzer_get_ctrl_block(BuzzerObjectTypeDef *self, BuzzerCtrlTypeDef *p) {
    // Simple queue implementation (could be enhanced with FreeRTOS queue)
    // For now, return empty (no queued commands)
    return -1; // No queued commands
}

static int buzzer_put_ctrl_block(BuzzerObjectTypeDef *self, BuzzerCtrlTypeDef *p) {
    // Direct execution for simplicity
    return 0;
}

static void buzzer_set_pwm(BuzzerObjectTypeDef *self, uint32_t freq) {
    // Configure PWM for buzzer on TIM4 Channel 2 (example)
    // Adapt to your actual hardware configuration
    // TIM4->CCR2 = (SystemCoreClock / (freq * 2)) - 1;
}

// ============================================================================
// LED HARDWARE ABSTRACTION
// ============================================================================

static int led_get_ctrl_block(LEDObjectTypeDef *self, LEDCtrlTypeDef *p) {
    // Simple queue implementation
    return -1; // No queued commands
}

static int led_put_ctrl_block(LEDObjectTypeDef *self, LEDCtrlTypeDef *p) {
    // Direct execution for simplicity
    return 0;
}

static void led_set_pin(LEDObjectTypeDef *self, uint32_t new_state) {
    // Configure LED GPIO (example: PD14)
    // Adapt to your actual hardware configuration
    GPIO_PinState pin_state = (new_state) ? GPIO_PIN_SET : GPIO_PIN_RESET;
    HAL_GPIO_WritePin(GPIOD, GPIO_PIN_14, pin_state);
}

// ============================================================================
// STATUS INITIALIZATION
// ============================================================================

int Status_Init(void) {
    // Initialize buzzer
    buzzer_object_init(&emergency_buzzer);
    emergency_buzzer.id = 0;
    emergency_buzzer.get_ctrl_block = buzzer_get_ctrl_block;
    emergency_buzzer.put_ctrl_block = buzzer_put_ctrl_block;
    emergency_buzzer.set_pwm = buzzer_set_pwm;
    
    // Initialize LED
    led_object_init(&status_led);
    status_led.id = 0;
    status_led.get_ctrl_block = led_get_ctrl_block;
    status_led.put_ctrl_block = led_put_ctrl_block;
    status_led.set_pin = led_set_pin;
    
    status_initialized = true;
    
    return 0; // Success
}

// ============================================================================
// STATUS UPDATE TASK (Call periodically)
// ============================================================================

void Status_Update(uint32_t period_ms) {
    if (!status_initialized) {
        return;
    }
    
    // Update buzzer state machine
    buzzer_task_handler(&emergency_buzzer, period_ms);
    
    // Update LED state machine
    led_task_handler(&status_led, period_ms);
}

// ============================================================================
// EMERGENCY INDICATIONS
// ============================================================================

void Status_EmergencyBeep(void) {
    if (!status_initialized) {
        return;
    }
    
    // Aggressive emergency beep sequence
    buzzer_didi(&emergency_buzzer, 2100, 100, 50, 10); // 2100Hz, 100ms on, 50ms off, 10 repeats
}

void Status_CommunicationLostBeep(void) {
    if (!status_initialized) {
        return;
    }
    
    // Communication lost pattern
    buzzer_didi(&emergency_buzzer, 1500, 200, 200, 5); // 1500Hz, 200ms on, 200ms off, 5 repeats
}

void Status_LowBatteryBeep(void) {
    if (!status_initialized) {
        return;
    }
    
    // Low battery warning
    buzzer_didi(&emergency_buzzer, 1200, 500, 500, 3); // 1200Hz, 500ms on, 500ms off, 3 repeats
}

void Status_OKBeep(void) {
    if (!status_initialized) {
        return;
    }
    
    // System OK acknowledgment
    buzzer_didi(&emergency_buzzer, 2000, 100, 100, 2); // 2000Hz, 100ms on, 100ms off, 2 repeats
}

// ============================================================================
// LED STATUS INDICATIONS
// ============================================================================

void Status_SetLEDNormal(void) {
    if (!status_initialized) {
        return;
    }
    
    led_on(&status_led); // Solid on = normal operation
}

void Status_SetLEDWarning(void) {
    if (!status_initialized) {
        return;
    }
    
    led_flash(&status_led, 500, 500, 0); // 500ms flash = warning
}

void Status_SetLEDEmergency(void) {
    if (!status_initialized) {
        return;
    }
    
    led_flash(&status_led, 100, 100, 0); // 100ms flash = emergency
}

void Status_SetLEDOff(void) {
    if (!status_initialized) {
        return;
    }
    
    led_off(&status_led);
}

// ============================================================================
// SYSTEM STARTUP INDICATION
// ============================================================================

void Status_StartupSequence(void) {
    if (!status_initialized) {
        return;
    }
    
    // Visual startup sequence
    for (int i = 0; i < 3; i++) {
        led_on(&status_led);
        HAL_Delay(200);
        led_off(&status_led);
        HAL_Delay(200);
    }
    
    // Audible startup acknowledgment
    Status_OKBeep();
}