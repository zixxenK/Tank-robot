#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "protocol_def.h"
#include "protocol_gateway.h"

static uint32_t g_dispatch_count = 0u;

static void test_handler(uint8_t function_code,
                         const uint8_t *payload,
                         uint8_t payload_len)
{
  (void)payload;
  (void)payload_len;
  printf("dispatch func=0x%02X len=%u\n", function_code, payload_len);
  g_dispatch_count++;
}

static size_t feed_bytes(const uint8_t *data,
                         size_t len,
                         uint32_t start_ms,
                         uint32_t step_ms,
                         uint8_t *forward,
                         size_t forward_cap)
{
  size_t total = 0u;
  uint32_t now_ms = start_ms;

  for (size_t i = 0u; i < len; ++i)
  {
    uint8_t out[64];
    size_t out_len = protocol_gateway_consume_byte(data[i], now_ms, out, sizeof(out));
    if (out_len > 0u && total < forward_cap)
    {
      size_t copy_len = out_len;
      if ((total + copy_len) > forward_cap)
      {
        copy_len = forward_cap - total;
      }
      memcpy(&forward[total], out, copy_len);
      total += copy_len;
    }

    now_ms += step_ms;
  }

  return total;
}

static void test_valid_frame(void)
{
  uint8_t payload[4] = {10u, 0u, 20u, 0u};
  uint8_t body[6] = {PROTO_FUNC_MOTOR_SET_BOTH, 4u, 10u, 0u, 20u, 0u};
  uint8_t frame[9] = {
    PROTO_SYNC_1,
    PROTO_SYNC_2,
    PROTO_FUNC_MOTOR_SET_BOTH,
    4u,
    payload[0],
    payload[1],
    payload[2],
    payload[3],
    protocol_crc8_ccitt(body, sizeof(body)),
  };
  uint8_t forward[64] = {0};
  size_t forward_len = 0u;

  protocol_gateway_reset();
  g_dispatch_count = 0u;
  forward_len = feed_bytes(frame, sizeof(frame), 1000u, 1u, forward, sizeof(forward));

  printf("[valid] dispatch=%u forward=%u\n",
         (unsigned)g_dispatch_count,
         (unsigned)forward_len);
}

static void test_vendor_motor_frame(void)
{
  uint8_t payload[12] = {
    PROTO_MOTOR_SUBCMD_SET_SPEED,
    2u,
    0u,
    0x00u, 0x00u, 0x00u, 0x3Fu,
    1u,
    0x00u, 0x00u, 0x00u, 0xBFu,
  };
  uint8_t frame[17];
  uint8_t forward[64] = {0};
  size_t forward_len = 0u;

  frame[0] = PROTO_SYNC_1;
  frame[1] = PROTO_SYNC_2;
  frame[2] = PROTO_FUNC_MOTOR;
  frame[3] = (uint8_t)sizeof(payload);
  memcpy(&frame[4], payload, sizeof(payload));
  frame[16] = protocol_crc8_ccitt(&frame[2], 2u + sizeof(payload));

  protocol_gateway_reset();
  g_dispatch_count = 0u;
  forward_len = feed_bytes(frame, sizeof(frame), 1500u, 1u, forward, sizeof(forward));

  printf("[vendor-motor] dispatch=%u forward=%u\n",
         (unsigned)g_dispatch_count,
         (unsigned)forward_len);
}

static void test_false_positive_recovery(void)
{
  uint8_t bytes[] = {
    0x01u,
    PROTO_SYNC_1,
    PROTO_SYNC_2,
    0x7Fu,
    0x22u,
    0x33u,
  };
  uint8_t forward[64] = {0};

  protocol_gateway_reset();
  g_dispatch_count = 0u;
  size_t forward_len = feed_bytes(bytes, sizeof(bytes), 2000u, 1u, forward, sizeof(forward));

  printf("[false-positive] dispatch=%u forward=%u\n",
         (unsigned)g_dispatch_count,
         (unsigned)forward_len);
}

static void test_timeout_recovery(void)
{
  uint8_t partial[] = {
    PROTO_SYNC_1,
    PROTO_SYNC_2,
    PROTO_FUNC_MOTOR_SET_BOTH,
    4u,
    0x11u,
  };
  uint8_t next = 0x42u;
  uint8_t forward[64] = {0};

  protocol_gateway_reset();
  g_dispatch_count = 0u;
  size_t forward_len = feed_bytes(partial,
                                  sizeof(partial),
                                  3000u,
                                  1u,
                                  forward,
                                  sizeof(forward));

  /* Force timeout gap and feed one new byte to trigger recovery flush. */
  {
    uint8_t out[64] = {0};
    size_t out_len = protocol_gateway_consume_byte(next,
                                                   3000u + PROTO_PARSER_TIMEOUT_MS + 5u,
                                                   out,
                                                   sizeof(out));
    if (out_len > 0u && forward_len < sizeof(forward))
    {
      size_t copy_len = out_len;
      if ((forward_len + copy_len) > sizeof(forward))
      {
        copy_len = sizeof(forward) - forward_len;
      }
      memcpy(&forward[forward_len], out, copy_len);
      forward_len += copy_len;
    }
  }

  printf("[timeout] dispatch=%u forward=%u\n",
         (unsigned)g_dispatch_count,
         (unsigned)forward_len);
}

static void test_fuzz_stream(void)
{
  uint8_t fuzz[256];
  uint8_t forward[1024] = {0};

  for (size_t i = 0u; i < sizeof(fuzz); ++i)
  {
    fuzz[i] = (uint8_t)(rand() & 0xFFu);
  }

  protocol_gateway_reset();
  g_dispatch_count = 0u;
  size_t forward_len = feed_bytes(fuzz, sizeof(fuzz), 4000u, 1u, forward, sizeof(forward));

  printf("[fuzz] dispatch=%u forward=%u\n",
         (unsigned)g_dispatch_count,
         (unsigned)forward_len);
}

int main(void)
{
  srand(42u);
  protocol_gateway_set_handler(test_handler);

  test_valid_frame();
  test_vendor_motor_frame();
  test_false_positive_recovery();
  test_timeout_recovery();
  test_fuzz_stream();

  return 0;
}