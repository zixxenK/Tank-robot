#include "cubemx_transport.h"

#include "protocol_def.h"
#include "protocol_gateway.h"

#include <string.h>

#include "stm32f4xx_hal.h"

#include "uxr/client/profile/transport/custom/custom_transport.h"

#define TRANSPORT_RX_CHUNK_SIZE 256U
#define TRANSPORT_RX_RING_SIZE   512U

static UART_HandleTypeDef *s_transport_huart = NULL;
static uint8_t s_rx_chunk[TRANSPORT_RX_CHUNK_SIZE];
static uint8_t s_rx_ring[TRANSPORT_RX_RING_SIZE];
static volatile size_t s_rx_head = 0U;
static volatile size_t s_rx_tail = 0U;
static volatile uint8_t s_rx_active = 0U;

static size_t ring_count(void)
{
  size_t head = s_rx_head;
  size_t tail = s_rx_tail;
  if (head >= tail)
  {
    return head - tail;
  }
  return TRANSPORT_RX_RING_SIZE - (tail - head);
}

static void ring_push(const uint8_t *data, size_t len)
{
  for (size_t i = 0U; i < len; ++i)
  {
    size_t next = (s_rx_head + 1U) % TRANSPORT_RX_RING_SIZE;
    if (next == s_rx_tail)
    {
      s_rx_tail = (s_rx_tail + 1U) % TRANSPORT_RX_RING_SIZE;
    }
    s_rx_ring[s_rx_head] = data[i];
    s_rx_head = next;
  }
}

static size_t ring_pop(uint8_t *data, size_t len)
{
  size_t copied = 0U;

  while (copied < len && ring_count() > 0U)
  {
    data[copied] = s_rx_ring[s_rx_tail];
    s_rx_tail = (s_rx_tail + 1U) % TRANSPORT_RX_RING_SIZE;
    ++copied;
  }

  return copied;
}

void cubemx_transport_init(UART_HandleTypeDef *huart)
{
  s_transport_huart = huart;
  s_rx_head = 0U;
  s_rx_tail = 0U;
  s_rx_active = 0U;
  protocol_gateway_reset();
}

bool cubemx_transport_open(struct uxrCustomTransport *transport)
{
  (void)transport;

  if (s_transport_huart == NULL)
  {
    return false;
  }

  s_rx_head = 0U;
  s_rx_tail = 0U;
  s_rx_active = 1U;

  if (HAL_UARTEx_ReceiveToIdle_DMA(s_transport_huart,
                                   s_rx_chunk,
                                   TRANSPORT_RX_CHUNK_SIZE) != HAL_OK)
  {
    s_rx_active = 0U;
    return false;
  }

  if (s_transport_huart->hdmarx != NULL)
  {
    __HAL_DMA_DISABLE_IT(s_transport_huart->hdmarx, DMA_IT_HT);
  }

  return true;
}

bool cubemx_transport_close(struct uxrCustomTransport *transport)
{
  (void)transport;

  if (s_transport_huart == NULL)
  {
    return false;
  }

  s_rx_active = 0U;
  (void)HAL_UART_DMAStop(s_transport_huart);
  return true;
}

size_t cubemx_transport_write(struct uxrCustomTransport *transport,
                              const uint8_t *buf,
                              size_t len,
                              uint8_t *err)
{
  (void)transport;

  if (s_transport_huart == NULL)
  {
    if (err != NULL)
    {
      *err = 1U;
    }
    return 0U;
  }

  if (HAL_UART_Transmit(s_transport_huart, (uint8_t *)buf, (uint16_t)len, 100) != HAL_OK)
  {
    if (err != NULL)
    {
      *err = 1U;
    }
    return 0U;
  }

  if (err != NULL)
  {
    *err = 0U;
  }

  return len;
}

size_t cubemx_transport_read(struct uxrCustomTransport *transport,
                             uint8_t *buf,
                             size_t len,
                             int timeout,
                             uint8_t *err)
{
  (void)transport;

  uint32_t start = HAL_GetTick();
  size_t received = 0U;

  while (received < len)
  {
    uint32_t now = HAL_GetTick();
    if ((now - start) > (uint32_t)timeout)
    {
      break;
    }

    if (ring_count() > 0U)
    {
      received += ring_pop(&buf[received], len - received);
      continue;
    }

    HAL_Delay(1);
  }

  if (received == len)
  {
    if (err != NULL)
    {
      *err = 0U;
    }
  }
  else
  {
    if (err != NULL)
    {
      *err = 1U;
    }
  }

  return received;
}

void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t size)
{
  if (huart == s_transport_huart && s_rx_active != 0U)
  {
    uint32_t now_ms = HAL_GetTick();

    for (uint16_t i = 0u; i < size; ++i)
    {
      uint8_t passthrough[2u + 1u + 1u + PROTO_MAX_PAYLOAD_LEN + 1u];
      size_t passthrough_len = protocol_gateway_consume_byte(s_rx_chunk[i],
                                                             now_ms,
                                                             passthrough,
                                                             sizeof(passthrough));
      if (passthrough_len > 0u)
      {
        ring_push(passthrough, passthrough_len);
      }
    }

    (void)HAL_UARTEx_ReceiveToIdle_DMA(s_transport_huart,
                                       s_rx_chunk,
                                       TRANSPORT_RX_CHUNK_SIZE);

    if (s_transport_huart->hdmarx != NULL)
    {
      __HAL_DMA_DISABLE_IT(s_transport_huart->hdmarx, DMA_IT_HT);
    }
  }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
  if (huart == s_transport_huart && s_rx_active != 0U)
  {
    (void)HAL_UARTEx_ReceiveToIdle_DMA(s_transport_huart,
                                       s_rx_chunk,
                                       TRANSPORT_RX_CHUNK_SIZE);
    if (s_transport_huart->hdmarx != NULL)
    {
      __HAL_DMA_DISABLE_IT(s_transport_huart->hdmarx, DMA_IT_HT);
    }
  }
}