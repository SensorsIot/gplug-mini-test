/* Composition root (docs/Method/project/architecture.md). Phase 1 skeleton:
 * it proves the build pipeline and emits the startup marker; the FSD
 * components are wired in here as /build implements them. */
#include "esp_log.h"
#include "udp_log.h"

static const char *TAG = "main";

void app_main(void)
{
    udp_log_init();
    ESP_LOGI(TAG, "Init complete")   /* DEMO: missing semicolon */
}
