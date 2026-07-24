#include "adc.h"
#include "global.h"
#include "global_conf.h"
#include "buzzer.h"

float battery_volt = 0.0f; /* 电池电压全局变量, 单位 v */
static uint16_t adc_value[2];

#if ENABLE_BLUETOOTH&&ENABLE_BLUETOOTH_BATTERY_REPORT /* 开启蓝牙电压报告后引入 */
extern osMessageQueueId_t bluetooth_tx_queueHandle; /* 蓝牙数据发送队列 */
#endif


void battery_check_timer_callback(void *argument)
{
	if(adc_value[0] != 0 && adc_value[0] != 4095) {
	    float volt = 1210.0f / ((float)adc_value[0]) * ((float)adc_value[1]) * 11.0f ; /* 1210.0是内部参考电压值， 100k + 10k 电阻分压， 实际电压是测量电压的11倍 */
		volt = volt > 20000 ? 0 : volt;
        battery_volt = battery_volt == 0 ? volt : battery_volt * 0.95f + volt * 0.05f;
    }
//	printf("%d\r\n", adc_value[0]);
    HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_value, 2);

#if  ENABLE_BLUETOOTH&&ENABLE_BLUETOOTH_BATTERY_REPORT
	static int battery_report_count = 0;
	battery_report_count++;
	if(battery_report_count > (int)(1 * 1000 / BATTERY_TASK_PERIOD)) { /* 定时发送蓝牙电压报告 */
		battery_report_count = 0;
		char msg[8];
		sprintf(&msg[1], "V%dV", (int)(battery_volt + 0.5f)); /* 组织蓝牙电量消息 */
//		printf("%s\r\n", &msg[1]);
		msg[0] = strlen(&msg[1]);
		osMessageQueuePut(bluetooth_tx_queueHandle, msg, 0, 0); /* 压入发送队列 */
	}
#endif

	
#if ENABLE_BATTERY_LOW_ALARM
	static int count = 0;
    if(battery_volt < BATTERY_LOW_ALARM_THRESHOLD && battery_volt > 4900) {
        count++;
    } else {
        count = 0;
    }
    if(count > (int)(10 * 1000 / BATTERY_TASK_PERIOD)) { /* 每 10s 触发一次警报声 */
        buzzer_didi(buzzers[0], 2100, 800, 200, 5);
        count = 0;
    }
#endif
}
