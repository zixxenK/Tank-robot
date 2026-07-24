#include <errno.h>
#include <stdint.h>
#include <time.h>

#include "stm32f4xx_hal.h"

#ifndef CLOCK_REALTIME
#define CLOCK_REALTIME 0
#endif

#ifndef CLOCK_MONOTONIC
#define CLOCK_MONOTONIC CLOCK_REALTIME
#endif

#ifndef CLOCK_MONOTONIC_RAW
#define CLOCK_MONOTONIC_RAW CLOCK_REALTIME
#endif

int clock_gettime(clockid_t clk_id, struct timespec *tp)
{
  (void)clk_id;

  if (tp == NULL) {
    errno = EINVAL;
    return -1;
  }

  uint32_t now_ms = HAL_GetTick();
  tp->tv_sec = (time_t)(now_ms / 1000U);
  tp->tv_nsec = (long)((now_ms % 1000U) * 1000000UL);
  return 0;
}