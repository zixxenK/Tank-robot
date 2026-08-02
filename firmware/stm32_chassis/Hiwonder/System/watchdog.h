#ifndef WATCHDOG_H
#define WATCHDOG_H

#include <stdbool.h>

void Watchdog_CaptureResetCause(void);
bool Watchdog_Init(void);
void Watchdog_Refresh(void);
bool Watchdog_WasReset(void);

#endif