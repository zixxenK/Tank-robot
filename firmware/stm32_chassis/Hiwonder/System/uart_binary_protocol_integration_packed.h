/**
 * @file uart_binary_protocol_integration_packed.h
 * @brief Integration header for packed binary protocol with STM32 firmware
 */

#ifndef UART_BINARY_PROTOCOL_INTEGRATION_PACKED_H
#define UART_BINARY_PROTOCOL_INTEGRATION_PACKED_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

// ============================================================================
// FUNCTION PROTOTYPES
// ============================================================================

/**
 * @brief Initialize packed binary protocol integration
 * Call this from your main() or initialization function
 * Configures timers and protocol state for the USART1/WCH motor transport
 * on PA9/PA10 (the product connector is labeled UART1).
 */
void binary_protocol_integration_init_packed(void);

/**
 * @brief Process transport buffer (call from the application task)
 * Processes bytes received by USART1 HAL idle-event DMA.
 */
void binary_protocol_process_dma_buffer(void);

/**
 * @brief Main protocol task (call from main loop or FreeRTOS task)
 * Handles:
 * - DMA buffer processing
 * - Timeout checking
 * - Motor command processing
 * - Motor PID update and watchdog refresh
 */
void binary_protocol_main_task(void);

/**
 * @brief Sample sensors and enqueue telemetry at 50Hz
 */
void binary_protocol_telemetry_task(void);

/**
 * @brief Trigger emergency stop (external trigger)
 * Call this from hardware emergency stop button or safety system
 */
void binary_protocol_trigger_emergency_stop(void);

/**
 * @brief Get protocol diagnostics
 * @return Pointer to statistics structure
 */
const void* binary_protocol_get_diagnostics(void);

/**
 * @brief Reset protocol diagnostics
 */
void binary_protocol_reset_diagnostics(void);

// ============================================================================
// FREERTOS TASK (Optional)
// ============================================================================

/**
 * @brief FreeRTOS task for protocol handling
 * @param argument Task argument (unused)
 */
void binary_protocol_task(void *argument);

#ifdef __cplusplus
}
#endif

#endif /* UART_BINARY_PROTOCOL_INTEGRATION_PACKED_H */
