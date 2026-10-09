#include "udp_log.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/message_buffer.h"
#include "freertos/task.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"

#define MSG_BUF_SIZE 4096
#define MAX_LINE     256

static const char *TAG = "udp_log";

static MessageBufferHandle_t s_buf;
static vprintf_like_t s_serial_vprintf;
static volatile uint32_t s_ip;      /* 0 = no target yet */
static volatile uint16_t s_port;

/* Serial always gets the line. The queue send never blocks: a full buffer
 * drops the line rather than stalling the task that logged (FR-LOG-02). */
static int udp_log_vprintf(const char *fmt, va_list args)
{
    va_list copy;
    va_copy(copy, args);
    int ret = s_serial_vprintf(fmt, args);
    if (s_ip != 0) {
        char line[MAX_LINE];
        int len = vsnprintf(line, sizeof(line), fmt, copy);
        if (len > 0) {
            if (len >= (int)sizeof(line)) {
                len = sizeof(line) - 1;
            }
            xMessageBufferSend(s_buf, line, (size_t)len, 0);
        }
    }
    va_end(copy);
    return ret;
}

/* The socket is opened on the first line, not at task start: lines are only
 * queued once a target is set, which needs an IP, so the TCP/IP stack is up by
 * then. A socket() before esp_netif_init() asserts in lwIP (Invalid mbox). */
static void udp_sender_task(void *arg)
{
    int sock = -1;
    char line[MAX_LINE];
    for (;;) {
        size_t len = xMessageBufferReceive(s_buf, line, sizeof(line), portMAX_DELAY);
        if (len == 0 || s_ip == 0) {
            continue;
        }
        if (sock < 0) {
            sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
            if (sock < 0) {
                continue;
            }
        }
        struct sockaddr_in dest = {
            .sin_family = AF_INET,
            .sin_port = htons(s_port),
            .sin_addr.s_addr = s_ip,
        };
        /* An unreachable target is not an error worth reporting: logging it
         * would feed the same failing path. */
        sendto(sock, line, len, 0, (struct sockaddr *)&dest, sizeof(dest));
    }
}

void udp_log_init(void)
{
    s_buf = xMessageBufferCreate(MSG_BUF_SIZE);
    if (s_buf == NULL) {
        ESP_LOGE(TAG, "message buffer allocation failed (%d bytes)", MSG_BUF_SIZE);
        return;
    }
    xTaskCreate(udp_sender_task, "udp_log", 3072, NULL, 2, NULL);
    s_serial_vprintf = esp_log_set_vprintf(udp_log_vprintf);
}

void udp_log_set_target(uint32_t ipv4, uint16_t port)
{
    s_port = port;
    s_ip = ipv4;
    struct in_addr addr = { .s_addr = ipv4 };
    ESP_LOGI(TAG, "UDP logging -> %s:%d", inet_ntoa(addr), port);
}
