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
    (void)argument;
    /* The production packed protocol task owns MPU6050 initialization,
     * polling, and UART telemetry.  This legacy task previously initialized
     * a second MPU6050 object and issued DMA reads on the same I2C2 bus,
     * contending with the protocol task and starving /stm32/imu. Keep the
     * generated task slot alive, but never access the shared sensor here. */
    for(;;) {
        osDelay(1000);
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

