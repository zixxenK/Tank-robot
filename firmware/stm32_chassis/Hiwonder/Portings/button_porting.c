/**
 * @file button_portting.c
 * @author Lu Yongping (Lucas@hiwonder.com)
 * @brief 板载按键接口实例及接口
 * @version 0.1
 * @date 2023-05-18
 *
 * @copyright Copyright (c) 2023
 *
 */

#include "button.h"
#include "global_conf.h"
#include "packet_reports.h"
#include "cmsis_os2.h"
#include "stm32f4xx.h"
#include "gpio.h"
#include "lwmem_porting.h"

// 全系统全局变量
ButtonObjectTypeDef* buttons[2];
static uint32_t button_read_pin(ButtonObjectTypeDef *self); /* 读取按键IO状态 */


void buttons_init(void)
{
	for(int i = 0; i < 2; ++i) {
		buttons[i] = LWMEM_CCM_MALLOC(sizeof(ButtonObjectTypeDef));
		button_object_init(buttons[i]);
		buttons[i]->id = i + 1;
	    buttons[i]->read_pin = button_read_pin;
		buttons[i]->combin_th = 300; 
		buttons[i]->lp_th = 1500;  
		buttons[i]->repeat_th = 400;
	}
}

static uint32_t button_read_pin(ButtonObjectTypeDef *self)
{
    switch(self->id) {
        case 1:
            return ((uint32_t)HAL_GPIO_ReadPin(KEY1_GPIO_Port, KEY1_Pin)) ^ 1;
        case 2:
            return ((uint32_t)HAL_GPIO_ReadPin(KEY2_GPIO_Port, KEY2_Pin)) ^ 1;
        default:
            return 0;
    }
}



/**
 * @brief 定时器回调进行按键扫描
 *
 * @param argument
 */
void button_timer_callback(void *argument)
{
	button_task_handler(buttons[0], BUTTON_TASK_PERIOD);
	button_task_handler(buttons[1], BUTTON_TASK_PERIOD);
}


//extern osMessageQueueId_t lvgl_event_queueHandle;
//static void key_event_callback(KeyObjectTypeDef* self, KeyEventEnum event)
//{
//    KeyEventObjectTypeDef *event_obj = LWMEM_CCM_MALLOC(sizeof(KeyEventObjectTypeDef));
//  event_obj->base.type = &type_key_event_instant;

//    struct PacketReportKeyEvent report = {
//        .event = (uint8_t)(int)event,
//    };
//    event_obj->event = event;
//    if(keys[0] == self) {
//        report.key_id = 1;
//        event_obj->key_id = 1;

//    }
//    if(keys[1] == self) {
//        report.key_id = 2;
//        event_obj->key_id = 2;
//    }
//    if(osMessageQueuePut(lvgl_event_queueHandle, &event_obj, 0, 0) != osOK) {
//        LWMEM_FREE(event_obj);
//    };
//    packet_transmit(&packet_controller, PACKET_FUNC_KEY, &report, sizeof(struct PacketReportKeyEvent));
//}



