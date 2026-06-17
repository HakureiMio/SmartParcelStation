#include "display_ui.h"

#include "app_config.h"
#include "esp_log.h"

static const char *TAG = "display_ui";

static void show_text(const char *text)
{
    ESP_LOGI(TAG, "%s", text);
}

esp_err_t display_ui_init(void)
{
    /*
     * TODO：待 WT9932P4-TINY 的 BSP 和 ST7701S MIPI DSI 初始化序列确认后，
     * 将这里替换为真实屏幕文本显示。当前先保留日志 stub，保证 ESP8266、
     * PN532 和 HTTP 上报主流程可以独立联调。
     */
    ESP_LOGW(TAG, "显示屏暂用日志 stub：%dx%d ST7701S MIPI DSI 待硬件确认",
             SPS_DISPLAY_WIDTH,
             SPS_DISPLAY_HEIGHT);
    return ESP_OK;
}

void display_ui_show_booting(void)
{
    show_text("SPS Gate P4 booting...");
}

void display_ui_show_network_status(const char *text)
{
    show_text(text);
}

void display_ui_show_pn532_status(const char *text)
{
    show_text(text);
}

void display_ui_show_wait_card(void)
{
    show_text("Tap card");
}

void display_ui_show_uid(const char *uid)
{
    ESP_LOGI(TAG, "UID: %s", uid);
}

void display_ui_show_uploading(void)
{
    show_text("Uploading UID...");
}

void display_ui_show_access_result(const gateway_access_result_t *result)
{
    if (result != NULL && result->access_granted) {
        show_text("Access granted");
    } else {
        show_text("Access denied");
    }
}

void display_ui_show_error(const char *title, const char *detail)
{
    ESP_LOGE(TAG, "%s: %s", title, detail == NULL ? "" : detail);
}
