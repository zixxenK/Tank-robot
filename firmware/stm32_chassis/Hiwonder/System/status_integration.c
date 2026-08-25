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

/* Sea Shanty 2 (OSRS) startup hook. This is the complete A-D transcription:
 * main theme, high synth, accordion breakdown, and flute climax. Duration
 * values follow the supplied Arduino convention: 2=half, 4=quarter,
 * 8=eighth, 16=sixteenth, and negative values are dotted. */
typedef struct {
    uint16_t frequency;
    int8_t duration_value;
} StartupSongNote;

static const StartupSongNote startup_song[] = {
    /* Section A: main theme */
    {880, 8}, {659, 8}, {587, 8}, {554, -4},
    {554, 8}, {587, 8}, {659, 8}, {740, 8}, {831, 8}, {659, -4},
    {0, 4},
    {740, 8}, {659, 8}, {587, 8}, {554, -4},
    {554, 8}, {494, 8}, {554, 8}, {587, 2}, {0, 4},
    {880, 8}, {659, 8}, {587, 8}, {554, -4},
    {554, 8}, {587, 8}, {659, 8}, {740, 4}, {587, 4}, {0, 4},
    {740, 8}, {659, 8}, {587, 8}, {554, 4}, {494, 8},
    {554, 8}, {587, 4}, {740, 8}, {659, 8}, {554, 8}, {494, 8},
    {440, 2}, {0, 4},

    /* Section B: high synth lead counter-melody */
    {880, 8}, {988, 8}, {1109, 4}, {1109, 8}, {988, 8}, {880, 8}, {831, 4},
    {659, 8}, {740, 8}, {831, 4}, {831, 8}, {740, 8}, {659, 8}, {587, 4},
    {554, 8}, {587, 8}, {659, 4}, {554, 8}, {587, 8}, {659, 8}, {740, 8},
    {659, 8}, {587, 8}, {554, 8}, {494, 4}, {440, 2}, {0, 4},
    {880, 8}, {988, 8}, {1109, 4}, {1109, 8}, {988, 8}, {880, 8}, {831, 4},
    {659, 8}, {740, 8}, {831, 4}, {831, 8}, {740, 8}, {659, 8}, {587, 4},
    {554, 8}, {587, 8}, {659, 8}, {740, 8}, {831, 8}, {880, 8}, {988, 8}, {1109, 8},
    {1175, 4}, {1109, 4}, {880, 2}, {0, 4},

    /* Section C: accordion solo and breakdown */
    {740, 16}, {831, 16}, {880, 8}, {880, 8}, {831, 8}, {740, 8}, {659, 8},
    {554, 8}, {587, 8}, {659, 8}, {659, 8}, {587, 8}, {554, 8}, {494, 8},
    {587, 8}, {587, 8}, {554, 8}, {494, 8}, {440, 8}, {494, 8},
    {554, 8}, {587, 8}, {659, 8}, {740, 8}, {831, 8}, {880, 4},
    {740, 16}, {831, 16}, {880, 8}, {880, 8}, {831, 8}, {740, 8}, {659, 8},
    {554, 8}, {587, 8}, {659, 8}, {659, 8}, {587, 8}, {554, 8}, {494, 8},
    {554, 8}, {587, 8}, {659, 8}, {740, 8}, {831, 8}, {880, 8},
    {988, 8}, {1109, 8}, {1175, 4}, {1109, 4}, {880, 2}, {0, 4},

    /* Section D: high flute climax run */
    {1109, 8}, {1175, 8}, {1319, 4}, {1319, 8}, {1175, 8}, {1109, 8}, {988, 4},
    {831, 8}, {880, 8}, {988, 4}, {988, 8}, {880, 8}, {831, 8}, {740, 4},
    {659, 8}, {740, 8}, {831, 8}, {880, 8}, {988, 8}, {1109, 8}, {1175, 8}, {1319, 8},
    {1480, 4}, {1319, 4}, {1109, 4}, {988, 4}, {880, 2}, {0, 2},
};

#define STARTUP_SONG_BPM 102U
#define STARTUP_SONG_WHOLE_NOTE_MS ((60000UL * 4UL) / STARTUP_SONG_BPM)
#define STARTUP_SONG_ARTICULATION_MS 12U

static bool startup_song_active = false;
static uint32_t startup_song_elapsed_ms = 0U;
static uint32_t startup_song_index = 0U;

static uint32_t startup_song_duration_ms(int8_t duration_value) {
    uint32_t denominator = (uint32_t)(duration_value < 0 ?
                                      -duration_value : duration_value);
    uint32_t duration_ms = STARTUP_SONG_WHOLE_NOTE_MS / denominator;
    return duration_value < 0 ? (duration_ms * 3U) / 2U : duration_ms;
}

static void startup_song_start_note(void) {
    if (buzzers[0] == NULL || startup_song_index >=
            (sizeof(startup_song) / sizeof(startup_song[0]))) {
        return;
    }

    const StartupSongNote *note = &startup_song[startup_song_index];
    uint32_t total_ms = startup_song_duration_ms(note->duration_value);
    uint16_t next_frequency = 0U;
    if (startup_song_index + 1U <
            (sizeof(startup_song) / sizeof(startup_song[0]))) {
        next_frequency = startup_song[startup_song_index + 1U].frequency;
    }
    uint32_t gap_ms = (note->frequency > 0U &&
                       note->frequency == next_frequency) ?
                      STARTUP_SONG_ARTICULATION_MS : 0U;
    uint32_t on_ms = total_ms > gap_ms ? total_ms - gap_ms : total_ms;

    /* Queue one note/rest at a time; the buzzer queue has depth five. */
    (void)buzzer_didi(buzzers[0], note->frequency, on_ms, gap_ms, 1U);
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
        uint32_t note_duration_ms = startup_song_duration_ms(
            startup_song[startup_song_index].duration_value);
        if (startup_song_elapsed_ms >= note_duration_ms) {
            startup_song_elapsed_ms -= note_duration_ms;
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
