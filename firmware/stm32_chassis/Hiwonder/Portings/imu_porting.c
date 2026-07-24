#include "global.h"
#include "lwmem_porting.h"
#include "packet_reports.h"
#include "global_conf.h"
#include "imu.h"
#include "imu_mpu6050.h"

IMU_ObjectTypeDef *imus[1];

static int i2c_write_byte_to_mem(MPU6050ObjectTypeDef *self, uint8_t reg_addr, uint8_t data);
static int i2c_read_from_mem(MPU6050ObjectTypeDef *self, uint8_t reg_addr, uint32_t length, uint8_t *buf);
static void DelayMs(uint32_t ms);

void imus_init(void)
{
    MPU6050ObjectTypeDef *mpu6050 = LWMEM_CCM_MALLOC(sizeof(MPU6050ObjectTypeDef));
    mpu6050_object_init(mpu6050, MPU6050_DEV_ADDR_1);
    mpu6050->i2c_write_byte_to_mem = i2c_write_byte_to_mem;
    mpu6050->i2c_read_from_mem = i2c_read_from_mem;
    mpu6050->sleep_ms = DelayMs;
    imus[0] = (IMU_ObjectTypeDef*)mpu6050;
}

#if ENABLE_IMU
/**
 * @brief  imu task 入口函数
 *
 */

void imu_task_entry(void *argument)
{
    extern osSemaphoreId_t mpu6050_data_readyHandle;

    imus_init();
    imus[0]->reset(imus[0]);

//    int imu_report_interval = 1;
//    int count = 0;
//    struct PacketReportIMU report;
    for(;;) {
        osSemaphoreAcquire(mpu6050_data_readyHandle, osWaitForever);
        imus[0]->update(imus[0]);
//        count += 1;
//        if(count > imu_report_interval) {
//            count = 0;
//            report.quat.w = imu1.quat.element.w;
//            report.quat.x = imu1.quat.element.x;
//            report.quat.y = imu1.quat.element.y;
//            report.quat.z = imu1.quat.element.z;
//            packet_transmit(&packet_controller, PACKET_FUNC_IMU, &report, sizeof(struct PacketReportIMU));
//        }
    }
}

#endif


static int i2c_write_byte_to_mem(MPU6050ObjectTypeDef *self, uint8_t reg_addr, uint8_t data)
{
    return HAL_I2C_Mem_Write(&hi2c2, self->dev_addr << 1, reg_addr, I2C_MEMADD_SIZE_8BIT, &data, 1, 0xFF);
}

static int i2c_read_from_mem(MPU6050ObjectTypeDef *self, uint8_t reg_addr, uint32_t length, uint8_t *buf)
{
// return HAL_I2C_Mem_Read(&hi2c2, self->dev_addr << 1, reg_addr, I2C_MEMADD_SIZE_8BIT, buf, length, 0xFF);
    return HAL_I2C_Mem_Read_DMA(&hi2c2, self->dev_addr << 1, reg_addr, I2C_MEMADD_SIZE_8BIT, buf, length);
}

static void DelayMs(uint32_t ms)
{
    osDelay(ms);
}

