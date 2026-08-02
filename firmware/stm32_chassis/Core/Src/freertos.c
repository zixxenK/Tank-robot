#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"

#include "uart_binary_protocol_integration_packed.h"

typedef StaticTask_t osStaticThreadDef_t;

osThreadId_t defaultTaskHandle;
static uint32_t defaultTaskBuffer[256];
static osStaticThreadDef_t defaultTaskControlBlock;
static osThreadId_t telemetryTaskHandle;
static uint32_t telemetryTaskBuffer[256];
static osStaticThreadDef_t telemetryTaskControlBlock;

static const osThreadAttr_t defaultTaskAttributes = {
    .name = "controlTask",
    .cb_mem = &defaultTaskControlBlock,
    .cb_size = sizeof(defaultTaskControlBlock),
    .stack_mem = &defaultTaskBuffer[0],
    .stack_size = sizeof(defaultTaskBuffer),
    .priority = (osPriority_t)osPriorityNormal,
};

static const osThreadAttr_t telemetryTaskAttributes = {
    .name = "telemetryTask",
    .cb_mem = &telemetryTaskControlBlock,
    .cb_size = sizeof(telemetryTaskControlBlock),
    .stack_mem = &telemetryTaskBuffer[0],
    .stack_size = sizeof(telemetryTaskBuffer),
    .priority = (osPriority_t)osPriorityBelowNormal,
};

static void StartDefaultTask(void *argument);
static void StartTelemetryTask(void *argument);

void vApplicationIdleHook(void) {
}

void vApplicationTickHook(void) {
}

void MX_FREERTOS_Init(void) {
    defaultTaskHandle = osThreadNew(
        StartDefaultTask, NULL, &defaultTaskAttributes);
    if (defaultTaskHandle == NULL) {
        Error_Handler();
    }

    telemetryTaskHandle = osThreadNew(
        StartTelemetryTask, NULL, &telemetryTaskAttributes);
    if (telemetryTaskHandle == NULL) {
        Error_Handler();
    }
}

static void StartDefaultTask(void *argument) {
    (void)argument;

    for (;;) {
        binary_protocol_main_task();
        osDelay(10);
    }
}

static void StartTelemetryTask(void *argument) {
    (void)argument;

    for (;;) {
        binary_protocol_telemetry_task();
        osDelay(20);
    }
}