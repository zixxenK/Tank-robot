#ifndef MICROROS_TRANSPORT_H
#define MICROROS_TRANSPORT_H

#include <rcl/rcl.h>
#include <rcl/error.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <uxr/client/transport.h>

bool microros_transport_open(struct uxrCustomTransport * transport);
bool microros_transport_close(struct uxrCustomTransport * transport);
size_t microros_transport_write(struct uxrCustomTransport* transport, const uint8_t* buf, size_t len, uint8_t* err);
size_t microros_transport_read(struct uxrCustomTransport* transport, uint8_t* buf, size_t len, int timeout, uint8_t* err);

#endif // MICROROS_TRANSPORT_H