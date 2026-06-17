#include "gateway_client.h"

#include <stdio.h>
#include <string.h>
#include <strings.h>

#include "app_config.h"
#include "cJSON.h"
#include "esp_log.h"
#include "network_client.h"

static const char *TAG = "gateway";

static void copy_json_string(cJSON *root, const char *name, char *dest, size_t dest_size)
{
    cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (cJSON_IsString(item) && item->valuestring != NULL) {
        strlcpy(dest, item->valuestring, dest_size);
    }
}

static void stringify_warnings(cJSON *root, char *dest, size_t dest_size)
{
    cJSON *warnings = cJSON_GetObjectItemCaseSensitive(root, "warnings");
    dest[0] = '\0';

    if (cJSON_IsString(warnings) && warnings->valuestring != NULL) {
        strlcpy(dest, warnings->valuestring, dest_size);
        return;
    }

    if (!cJSON_IsArray(warnings)) {
        return;
    }

    size_t used = 0;
    cJSON *item = NULL;
    cJSON_ArrayForEach(item, warnings) {
        const char *text = cJSON_IsString(item) ? item->valuestring : NULL;
        if (text == NULL) {
            continue;
        }
        int written = snprintf(dest + used, dest_size - used, "%s%s", used == 0 ? "" : ",", text);
        if (written < 0 || (size_t)written >= dest_size - used) {
            dest[dest_size - 1] = '\0';
            return;
        }
        used += (size_t)written;
    }
}

static bool parse_access_value(cJSON *root)
{
    cJSON *access = cJSON_GetObjectItemCaseSensitive(root, "access");
    if (cJSON_IsBool(access)) {
        return cJSON_IsTrue(access);
    }
    if (cJSON_IsString(access) && access->valuestring != NULL) {
        const char *value = access->valuestring;
        return strcasecmp(value, "granted") == 0 || strcasecmp(value, "true") == 0 || strcmp(value, "1") == 0;
    }

    cJSON *allowed = cJSON_GetObjectItemCaseSensitive(root, "allowed");
    if (cJSON_IsBool(allowed)) {
        return cJSON_IsTrue(allowed);
    }

    return false;
}

static void parse_gateway_response(const char *body, gateway_access_result_t *result)
{
    cJSON *root = cJSON_Parse(body);
    if (root == NULL) {
        ESP_LOGW(TAG, "Gateway response JSON parse failed, raw response: %s", body);
        return;
    }

    result->access_granted = parse_access_value(root);
    copy_json_string(root, "pickup_session_id", result->pickup_session_id, sizeof(result->pickup_session_id));
    copy_json_string(root, "display_text", result->display_text, sizeof(result->display_text));
    stringify_warnings(root, result->warnings, sizeof(result->warnings));

    cJSON *pickup_count = cJSON_GetObjectItemCaseSensitive(root, "pickup_count");
    if (cJSON_IsNumber(pickup_count)) {
        result->pickup_count = pickup_count->valueint;
    }

    ESP_LOGI(TAG, "Gateway access %s", result->access_granted ? "granted" : "denied");
    ESP_LOGI(TAG, "pickup_count=%d", result->pickup_count);
    if (result->pickup_session_id[0] != '\0') {
        ESP_LOGI(TAG, "pickup_session_id=%s", result->pickup_session_id);
    }
    if (result->display_text[0] != '\0') {
        ESP_LOGI(TAG, "display_text=%s", result->display_text);
    }
    if (result->warnings[0] != '\0') {
        ESP_LOGW(TAG, "warnings=%s", result->warnings);
    }

    cJSON_Delete(root);
}

esp_err_t gateway_client_post_access_card(const char *uid_hex, gateway_access_result_t *result)
{
    if (uid_hex == NULL || result == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    memset(result, 0, sizeof(*result));
    result->pickup_count = -1;

    cJSON *root = cJSON_CreateObject();
    if (root == NULL) {
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddStringToObject(root, "reader_id", SPS_READER_ID);
    cJSON_AddStringToObject(root, "credential_type", "CARD_UID");
    cJSON_AddStringToObject(root, "credential_value", uid_hex);

    char *payload = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (payload == NULL) {
        return ESP_ERR_NO_MEM;
    }

    char response[SPS_HTTP_RESPONSE_MAX] = {0};
    esp_err_t err = network_client_http_post_json(
        SPS_GATEWAY_HOST,
        SPS_GATEWAY_PORT,
        SPS_GATEWAY_PATH,
        payload,
        response,
        sizeof(response),
        &result->http_status);
    cJSON_free(payload);

    result->request_ok = err == ESP_OK && result->http_status >= 200 && result->http_status < 300;
    if (!result->request_ok) {
        ESP_LOGE(TAG, "Gateway request failed, HTTP status=%d, body=%s", result->http_status, response);
        return err == ESP_OK ? ESP_FAIL : err;
    }

    parse_gateway_response(response, result);
    return ESP_OK;
}
