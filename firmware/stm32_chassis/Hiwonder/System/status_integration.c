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

extern BuzzerObjectTypeDef *buzzers[1];

// ============================================================================
// STATUS PERIPHERAL INSTANCES
// ============================================================================

static LEDObjectTypeDef status_led;

static bool status_initialized = false;

/* Sea Shanty 2 (OSRS) startup hook. Keep this in the firmware image so the
 * melody plays even when the Rock64 host stack has not started yet. */
static const uint16_t startup_song[] = {
    440, 554, 659, 740, 659, 554, 440, 554,
    659, 740, 440, 494, 440, 740, 659, 740,
    440, 494, 554, 587, 554, 494, 440, 740,
    659, 554, 494, 440, 740, 659, 554, 440,
};

#define STARTUP_SONG_NOTE_ON_MS  180U
#define STARTUP_SONG_NOTE_GAP_MS  40U

static bool startup_song_active = false;
static uint32_t startup_song_elapsed_ms = 0U;
static uint32_t startup_song_index = 0U;

static void startup_song_start_note(void) {
    if (buzzers[0] == NULL || startup_song_index >=
            (sizeof(startup_song) / sizeof(startup_song[0]))) {
        return;
    }

    /* Queue one note at a time; the buzzer queue has depth five. */
    (void)buzzer_didi(buzzers[0], startup_song[startup_song_index],
                      STARTUP_SONG_NOTE_ON_MS, STARTUP_SONG_NOTE_GAP_MS, 1U);
}

// ============================================================================
// LED HARDWARE ABSTRACTION
// ============================================================================

static int led_get_ctrl_block(LEDObjectTypeDef *self, LEDCtrlTypeDef *p) {
    (void)self;
    (void)p;
    // Simple queue implementation
    return -1; // No queued commands
}

static int led_put_ctrl_block(LEDObjectTypeDef *self, LEDCtrlTypeDef *p) {
    (void)self;
    (void)p;
    // Direct execution for simplicity
    return 0;
}

static void led_set_pin(LEDObjectTypeDef *self, uint32_t new_state) {
    (void)self;
    // Configure LED GPIO (example: PD14)
    // Adapt to your actual hardware configuration
    GPIO_PinState pin_state = (new_state) ? GPIO_PIN_SET : GPIO_PIN_RESET;
    HAL_GPIO_WritePin(GPIOD, GPIO_PIN_14, pin_state);
}

// ============================================================================
// STATUS INITIALIZATION
// ============================================================================

int Status_Init(void) {
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
    
    /* The buzzer state machine is owned by buzzer_timer_callback().  Keeping
     * this control-cadence task out of it avoids concurrent queue/state access. */
    if (startup_song_active) {
        startup_song_elapsed_ms += period_ms;
        if (startup_song_elapsed_ms >=
                (STARTUP_SONG_NOTE_ON_MS + STARTUP_SONG_NOTE_GAP_MS)) {
            startup_song_elapsed_ms -=
                (STARTUP_SONG_NOTE_ON_MS + STARTUP_SONG_NOTE_GAP_MS);
            startup_song_index++;
            if (startup_song_index >=
                    (sizeof(startup_song) / sizeof(startup_song[0]))) {
                startup_song_active = false;
                startup_song_elapsed_ms = 0U;
                (void)buzzer_off(buzzers[0]);
            } else {
                startup_song_start_note();
            }
        }
    }
    
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
    if (buzzers[0] != NULL) {
        buzzer_didi(buzzers[0], 2100, 100, 50, 10);
    }
}

void Status_CommunicationLostBeep(void) {
    if (!status_initialized) {
        return;
    }
    
    // Communication lost pattern
    if (buzzers[0] != NULL) {
        buzzer_didi(buzzers[0], 1500, 200, 200, 5);
    }
}

void Status_LowBatteryBeep(void) {
    if (!status_initialized) {
        return;
    }
    
    // Low battery warning
    if (buzzers[0] != NULL) {
        buzzer_didi(buzzers[0], 1200, 500, 500, 3);
    }
}

void Status_OKBeep(void) {
    if (!status_initialized) {
        return;
    }
    
    // System OK acknowledgment
    if (buzzers[0] != NULL) {
        buzzer_didi(buzzers[0], 2000, 100, 100, 2);
    }
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

void Status_PlayStartupSong(void) {
    if (!status_initialized || buzzers[0] == NULL) {
        return;
    }

    startup_song_index = 0U;
    startup_song_elapsed_ms = 0U;
    startup_song_active = true;
    startup_song_start_note();
}
