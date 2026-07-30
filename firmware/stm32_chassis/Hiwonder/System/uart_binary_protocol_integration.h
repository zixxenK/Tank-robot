/**
 * @file uart_binary_protocol_integration.h
 * @brief Integration header for binary protocol with STM32 firmware
 */

#ifndef UART_BINARY_PROTOCOL_INTEGRATION_H
#define UART_BINARY_PROTOCOL_INTEGRATION_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

// Function Prototypes

/**
 * @brief Initialize binary protocol integration
 * Call this from your main() or initialization function
 */
void binary_protocol_integration_init(void);

/**
 * @brief Periodic task for protocol integration
 * Call this from your main loop or a FreeRTOS task
 */
void binary_protocol_integration_periodic_task(void);

/**
 * @brief Update encoder telemetry
 * Call this periodically to read and send encoder data
 */
void update_encoder_telemetry(void);

/**
 * @brief Update battery telemetry
 * Call this periodically to read and send battery data
 */
void update_battery_telemetry(void);

/**
 * @brief Update IMU telemetry
 * Call this periodically to read and send IMU data
 */
void update_imu_telemetry(void);

/**
 * @brief Get protocol statistics for diagnostics
 * @return Pointer to protocol statistics structure
 */
const ProtocolStats* binary_protocol_integration_get_stats(void);

/**
 * @brief Emergency stop - called from safety systems
 */
void binary_protocol_integration_emergency_stop(void);

/**
 * @brief FreeRTOS task for protocol handling
 * Create this task in your FreeRTOS initialization if using RTOS
 * @param argument Task argument (unused)
 */
void binary_protocol_task(void *argument);

#ifdef __cplusplus
}
#endif

#endif /* UART_BINARY_PROTOCOL_INTEGRATION_H */
