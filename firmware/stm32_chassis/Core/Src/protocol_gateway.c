#include "protocol_gateway.h"

#include <string.h>

#include "protocol_def.h"

typedef enum
{
  PARSER_WAIT_SYNC_1 = 0,
  PARSER_WAIT_SYNC_2,
  PARSER_READ_FUNCTION,
  PARSER_READ_LENGTH,
  PARSER_READ_PAYLOAD,
  PARSER_READ_CRC,
} ParserState_t;

typedef struct
{
  ParserState_t state;
  uint32_t last_byte_ms;
  uint8_t function_code;
  uint8_t payload_len;
  uint8_t payload_index;
  uint8_t payload[PROTO_MAX_PAYLOAD_LEN];
  uint8_t frame_bytes[2u + 1u + 1u + PROTO_MAX_PAYLOAD_LEN + 1u];
  size_t frame_len;
} ProtocolGatewayParser_t;

static ProtocolGatewayParser_t s_parser;
static protocol_gateway_command_handler_t s_handler = NULL;

static int16_t expected_payload_len(uint8_t function_code)
{
  switch (function_code)
  {
    case PROTO_FUNC_LED:
      return 7;

    case PROTO_FUNC_BUZZER:
      return 8;

    case PROTO_FUNC_MOTOR:
    case PROTO_FUNC_PWM_SERVO:
    case PROTO_FUNC_BUS_SERVO:
      return -2;

    case PROTO_FUNC_HEARTBEAT:
    case PROTO_FUNC_SELF_TEST:
    case PROTO_FUNC_EMERGENCY_STOP:
      return 0;

    case PROTO_FUNC_MOTOR_SET_BOTH:
    case PROTO_FUNC_MOTOR_SET_SINGLE:
      return 4;

    default:
      return -1;
  }
}

static uint8_t is_valid_variable_length(uint8_t function_code,
                                        uint8_t payload_len)
{
  if (function_code == PROTO_FUNC_MOTOR)
  {
    /* subcmd + count + N*(motor_id + float32 speed) */
    if (payload_len < 2u)
    {
      return 0u;
    }

    return ((payload_len - 2u) % 5u) == 0u ? 1u : 0u;
  }

  if (function_code == PROTO_FUNC_PWM_SERVO ||
      function_code == PROTO_FUNC_BUS_SERVO)
  {
    /* Variable by subcommand, validated in command handler after CRC. */
    return payload_len >= 1u ? 1u : 0u;
  }

  return 0u;
}

static size_t append_forward(uint8_t *dst,
                             size_t dst_cap,
                             size_t dst_len,
                             const uint8_t *src,
                             size_t src_len)
{
  size_t copy_len = src_len;

  if (dst_len >= dst_cap)
  {
    return dst_len;
  }

  if ((dst_len + copy_len) > dst_cap)
  {
    copy_len = dst_cap - dst_len;
  }

  if (copy_len > 0u)
  {
    memcpy(&dst[dst_len], src, copy_len);
    dst_len += copy_len;
  }

  return dst_len;
}

static void parser_reset(void)
{
  s_parser.state = PARSER_WAIT_SYNC_1;
  s_parser.last_byte_ms = 0u;
  s_parser.function_code = 0u;
  s_parser.payload_len = 0u;
  s_parser.payload_index = 0u;
  s_parser.frame_len = 0u;
}

void protocol_gateway_reset(void)
{
  parser_reset();
}

void protocol_gateway_set_handler(protocol_gateway_command_handler_t handler)
{
  s_handler = handler;
}

size_t protocol_gateway_consume_byte(uint8_t byte,
                                     uint32_t now_ms,
                                     uint8_t *bytes_to_forward,
                                     size_t max_forward_len)
{
  size_t forward_len = 0u;

  if (s_parser.state != PARSER_WAIT_SYNC_1 && s_parser.last_byte_ms != 0u)
  {
    uint32_t elapsed = now_ms - s_parser.last_byte_ms;
    if (elapsed > PROTO_PARSER_TIMEOUT_MS)
    {
      forward_len = append_forward(bytes_to_forward,
                                   max_forward_len,
                                   forward_len,
                                   s_parser.frame_bytes,
                                   s_parser.frame_len);
      parser_reset();
    }
  }

  s_parser.last_byte_ms = now_ms;

  switch (s_parser.state)
  {
    case PARSER_WAIT_SYNC_1:
      if (byte == PROTO_SYNC_1)
      {
        s_parser.frame_bytes[0] = byte;
        s_parser.frame_len = 1u;
        s_parser.state = PARSER_WAIT_SYNC_2;
      }
      else
      {
        forward_len = append_forward(bytes_to_forward,
                                     max_forward_len,
                                     forward_len,
                                     &byte,
                                     1u);
      }
      break;

    case PARSER_WAIT_SYNC_2:
      if (byte == PROTO_SYNC_2)
      {
        s_parser.frame_bytes[s_parser.frame_len++] = byte;
        s_parser.state = PARSER_READ_FUNCTION;
      }
      else
      {
        uint8_t fallback[2u] = {PROTO_SYNC_1, byte};
        forward_len = append_forward(bytes_to_forward,
                                     max_forward_len,
                                     forward_len,
                                     fallback,
                                     sizeof(fallback));

        if (byte == PROTO_SYNC_1)
        {
          s_parser.frame_bytes[0] = byte;
          s_parser.frame_len = 1u;
          s_parser.state = PARSER_WAIT_SYNC_2;
        }
        else
        {
          parser_reset();
        }
      }
      break;

    case PARSER_READ_FUNCTION:
      s_parser.function_code = byte;
      s_parser.frame_bytes[s_parser.frame_len++] = byte;
      s_parser.state = PARSER_READ_LENGTH;
      break;

    case PARSER_READ_LENGTH:
    {
      int16_t expected_len = expected_payload_len(s_parser.function_code);

      s_parser.payload_len = byte;
      s_parser.payload_index = 0u;
      s_parser.frame_bytes[s_parser.frame_len++] = byte;

      if (expected_len == -2)
      {
        if (s_parser.payload_len > PROTO_MAX_PAYLOAD_LEN ||
            is_valid_variable_length(s_parser.function_code, s_parser.payload_len) == 0u)
        {
          forward_len = append_forward(bytes_to_forward,
                                       max_forward_len,
                                       forward_len,
                                       s_parser.frame_bytes,
                                       s_parser.frame_len);
          parser_reset();
        }
        else if (s_parser.payload_len == 0u)
        {
          s_parser.state = PARSER_READ_CRC;
        }
        else
        {
          s_parser.state = PARSER_READ_PAYLOAD;
        }
        break;
      }

      if (expected_len < 0)
      {
        forward_len = append_forward(bytes_to_forward,
                                     max_forward_len,
                                     forward_len,
                                     s_parser.frame_bytes,
                                     s_parser.frame_len);
        parser_reset();
      }
      else if (s_parser.payload_len > PROTO_MAX_PAYLOAD_LEN)
      {
        forward_len = append_forward(bytes_to_forward,
                                     max_forward_len,
                                     forward_len,
                                     s_parser.frame_bytes,
                                     s_parser.frame_len);
        parser_reset();
      }
      else if ((uint8_t)expected_len != s_parser.payload_len)
      {
        forward_len = append_forward(bytes_to_forward,
                                     max_forward_len,
                                     forward_len,
                                     s_parser.frame_bytes,
                                     s_parser.frame_len);
        parser_reset();
      }
      else if (s_parser.payload_len == 0u)
      {
        s_parser.state = PARSER_READ_CRC;
      }
      else
      {
        s_parser.state = PARSER_READ_PAYLOAD;
      }
      break;
    }

    case PARSER_READ_PAYLOAD:
      s_parser.payload[s_parser.payload_index++] = byte;
      s_parser.frame_bytes[s_parser.frame_len++] = byte;

      if (s_parser.payload_index >= s_parser.payload_len)
      {
        s_parser.state = PARSER_READ_CRC;
      }
      break;

    case PARSER_READ_CRC:
    {
      uint8_t expected_crc = protocol_crc8_ccitt(&s_parser.frame_bytes[2],
                                                 2u + s_parser.payload_len);
      s_parser.frame_bytes[s_parser.frame_len++] = byte;

      if (byte == expected_crc)
      {
        if (s_handler != NULL)
        {
          s_handler(s_parser.function_code, s_parser.payload, s_parser.payload_len);
        }
      }
      else
      {
        forward_len = append_forward(bytes_to_forward,
                                     max_forward_len,
                                     forward_len,
                                     s_parser.frame_bytes,
                                     s_parser.frame_len);
      }

      parser_reset();
      break;
    }

    default:
      parser_reset();
      break;
  }

  return forward_len;
}
