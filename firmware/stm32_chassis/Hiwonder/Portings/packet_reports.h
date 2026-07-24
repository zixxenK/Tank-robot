/**
 * @file packet_reports.h
 * @author Lu Yongping (Lucas@hiwonder.com)
 * @brief 所有串口通信数据回报
 * @version 0.1
 * @date 2023-05-31
 * 
 * @copyright Copyright (c) 2023
 * 
 */
#include <stdint.h>

#pragma pack(1)
struct PacketReportIMU {
    struct {
        float w;
        float x;
        float y;
        float z;
    }quat;
};

struct PacketReportKeyEvent {
    uint8_t key_id;
    uint8_t event;
};

#pragma pack()
