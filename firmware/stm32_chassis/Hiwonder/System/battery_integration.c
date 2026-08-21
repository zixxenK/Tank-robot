/**
 * @file battery_integration.c
 * @brief Battery/ADC integration with filter priming
 * 
 * CRITICAL IMPLEMENTATION NOTES:
 * 1. Filter buffer primed with first valid ADC read on boot
 * 2. Prevents false-positive low-voltage emergency stop during startup
 * 3. Uses one external battery ADC rank plus an internal VREFINT rank with DMA
 * 4. Voltage divider: 100k + 10k = 11x scaling
 * 5. ADC reference: 3.3V analog rail
 * 6. Thresholds match the documented 11.1V (3S) stock pack; this legacy
 *    monitor remains disabled in the current motor-only telemetry image.
 */

#include "battery_integration.h"
#include "adc.h"
#include "main.h"

// ============================================================================
// BATTERY CONFIGURATION
// ============================================================================

#define VOLTAGE_DIVIDER_RATIO   11.0f  // 100k + 10k resistor divider
#define ADC_REFERENCE_VOLTAGE   3.3f   // STM32 analog supply/reference
#define ADC_MAX_VALUE           4095   // 12-bit ADC
#define FILTER_ALPHA            0.05f  // Moving average filter (0.05 new, 0.95 old)
#define LOW_VOLTAGE_THRESHOLD_V 10.5f  // documented 11.1V (3S) pack warning
#define CRITICAL_VOLTAGE_V      9.5f   // documented 11.1V (3S) pack cutoff

// ============================================================================
// BATTERY STATE
// ============================================================================

static float battery_voltage = 0.0f;     // Current filtered voltage (V)
static float battery_current = 0.0f;    // Current reading (A) - if current sensing available
static bool current_sense_available = false; // Current sensor validity flag
static bool battery_initialized = false;
static bool filter_primed = false;

// ADC DMA buffer (two conversion ranks)
// [0] is the PB0 battery sense; [1] is internal VREFINT, not a second pack
// or a current-sense input.
static uint16_t adc_buffer[2] = {0, 0};

// ============================================================================
// FILTER PRIMING
// ============================================================================

/**
 * @brief Prime the moving average filter with first valid ADC read
 * 
 * CRITICAL: This prevents the battery voltage from starting at 0.0V
 * and ramping up over several seconds, which could trigger a false
 * positive low-voltage emergency stop during startup.
 */
static void prime_filter(void) {
    // Take multiple readings to get stable initial value
    float voltage_sum = 0.0f;
    const int prime_samples = 10;
    int valid_samples = 0;
    
    HAL_ADC_Start(&hadc1);
    for (int i = 0; i < prime_samples; i++) {
        // ADC1 is a two-rank sequence: PB0 battery voltage, then VREFINT.
        // Consume both conversions but only convert rank 1 as battery data.
        if (HAL_ADC_PollForConversion(&hadc1, 10) != HAL_OK) {
            HAL_Delay(10);
            continue;
        }
        uint16_t adc_raw = HAL_ADC_GetValue(&hadc1);

        if (HAL_ADC_PollForConversion(&hadc1, 10) != HAL_OK) {
            HAL_Delay(10);
            continue;
        }
        (void)HAL_ADC_GetValue(&hadc1); // discard rank 2 (internal VREFINT)
        
        // Convert to voltage
        float adc_voltage = (adc_raw / (float)ADC_MAX_VALUE) * ADC_REFERENCE_VOLTAGE;
        float battery_v = adc_voltage * VOLTAGE_DIVIDER_RATIO;
        
        voltage_sum += battery_v;
        valid_samples++;
        
        HAL_Delay(10); // Small delay between samples
    }
    HAL_ADC_Stop(&hadc1);
    
    // Initialize filter with average of priming samples
    battery_voltage = valid_samples > 0 ? voltage_sum / valid_samples : 0.0f;
    filter_primed = valid_samples > 0;
}

// ============================================================================
// BATTERY INITIALIZATION
// ============================================================================

int Battery_Init(void) {
    // Initialize ADC (already configured by STM32CubeMX)
    MX_ADC1_Init();
    
    // Prime the filter with initial readings
    prime_filter();
    
    // Start ADC DMA for continuous conversion
    HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_buffer, 2);
    
    battery_initialized = true;
    
    return 0; // Success
}

// ============================================================================
// BATTERY UPDATE
// ============================================================================

int Battery_Update(void) {
    if (!battery_initialized) {
        return -1; // Not initialized
    }
    
    // Check for valid ADC readings (filter out 0 and max values)
    if (adc_buffer[0] == 0 || adc_buffer[0] >= ADC_MAX_VALUE) {
        return -2; // Invalid ADC reading
    }
    
    // Convert raw ADC to voltage
    float adc_voltage = (adc_buffer[0] / (float)ADC_MAX_VALUE) * ADC_REFERENCE_VOLTAGE;
    float instant_voltage = adc_voltage * VOLTAGE_DIVIDER_RATIO;
    
    // Sanity check: voltage should be between 5V and 15V for the documented
    // 11.1V pack profile.
    if (instant_voltage < 5.0f || instant_voltage > 15.0f) {
        return -3; // Out of range
    }
    
    // Apply moving average filter
    if (filter_primed) {
        battery_voltage = battery_voltage * (1.0f - FILTER_ALPHA) + instant_voltage * FILTER_ALPHA;
    } else {
        battery_voltage = instant_voltage;
    }
    
    // No current-sense amplifier or second battery ADC is wired in this image.
    // Keep current telemetry explicitly unavailable rather than interpreting
    // the internal VREFINT conversion as a physical current channel.
    battery_current = 0.0f;
    current_sense_available = false;  // Set true only when INA219 or equivalent is wired to adc_buffer[1]
    
    return 0; // Success
}

// ============================================================================
// BATTERY STATE QUERIES
// ============================================================================

float Battery_GetVoltage(void) {
    return battery_voltage;
}

float Battery_GetCurrent(void) {
    return battery_current;
}

bool Battery_IsLowVoltage(void) {
    return (battery_voltage < LOW_VOLTAGE_THRESHOLD_V);
}

bool Battery_IsCriticalVoltage(void) {
    return (battery_voltage < CRITICAL_VOLTAGE_V);
}

bool Battery_IsReady(void) {
    return battery_initialized && filter_primed;
}

bool Battery_IsCurrentValid(void) {
    return current_sense_available;
}

// ============================================================================
// ADC CONVERSION COMPLETE CALLBACK (DMA)
// ============================================================================

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef* hadc) {
    if (hadc->Instance == ADC1) {
        // ADC DMA conversion complete
        // Data is automatically updated in adc_buffer by DMA
        // The Battery_Update() function will process this data
    }
}
