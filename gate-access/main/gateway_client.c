#include "gateway_client.h"

#include <stdio.h>
#include <string.h>
#include <strings.h>

#include "app_config.h"
#include "cJSON.h"
#include "esp_log.h"
#include "network_client.h"

static const char *TAG = "gateway";

/* Reusable HTTP response buffer (avoids stack allocation of 2048+ bytes). */
static char s_response[SPS_HTTP_RESPONSE_MAX];

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

    cJSON *status = cJSON_GetObjectItemCaseSensitive(root, "status");
    if (cJSON_IsString(status) && status->valuestring != NULL) {
        return strcasecmp(status->valuestring, "granted") == 0;
    }

    return false;
}

static void stringify_array(cJSON *root, const char *name, char *dest, size_t dest_size)
{
    dest[0] = '\0';
    cJSON *array = cJSON_GetObjectItemCaseSensitive(root, name);
    if (!cJSON_IsArray(array)) return;
    size_t used = 0;
    cJSON *item = NULL;
    cJSON_ArrayForEach(item, array) {
        if (!cJSON_IsString(item)) continue;
        int n = snprintf(dest + used, dest_size - used, "%s%s", used ? " " : "", item->valuestring);
        if (n < 0 || (size_t)n >= dest_size - used) break;
        used += (size_t)n;
    }
}

static void copy_json_scalar(cJSON *root, const char *name, char *dest, size_t dest_size)
{
    cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    if (cJSON_IsString(item) && item->valuestring != NULL) {
        strlcpy(dest, item->valuestring, dest_size);
    } else if (cJSON_IsNumber(item)) {
        snprintf(dest, dest_size, "%d", item->valueint);
    }
}

static void stringify_item_codes(cJSON *root, char *dest, size_t dest_size)
{
    dest[0] = '\0';
    cJSON *items = cJSON_GetObjectItemCaseSensitive(root, "items");
    if (!cJSON_IsArray(items)) return;
    size_t used = 0;
    cJSON *item = NULL;
    cJSON_ArrayForEach(item, items) {
        cJSON *code = cJSON_GetObjectItemCaseSensitive(item, "parcel_code");
        if (!cJSON_IsString(code) || code->valuestring == NULL) continue;
        int n = snprintf(dest + used, dest_size - used, "%s%s",
                         used ? " " : "", code->valuestring);
        if (n < 0 || (size_t)n >= dest_size - used) {
            dest[dest_size - 1] = '\0';
            break;
        }
        used += (size_t)n;
    }
}

static void parse_gateway_response(const char *body, gateway_access_result_t *result)
{
    cJSON *root = cJSON_Parse(body);
    if (root == NULL) {
        ESP_LOGW(TAG, "Gateway response JSON parse failed, raw response: %s", body);
        return;
    }

    result->access_granted = parse_access_value(root);
    copy_json_scalar(root, "user_id", result->user_id, sizeof(result->user_id));
    copy_json_string(root, "pickup_session_id", result->pickup_session_id, sizeof(result->pickup_session_id));
    copy_json_string(root, "display_text", result->display_text, sizeof(result->display_text));
    copy_json_string(root, "status", result->status, sizeof(result->status));
    copy_json_string(root, "reason", result->reason, sizeof(result->reason));
    copy_json_string(root, "session_color", result->session_color, sizeof(result->session_color));
    stringify_array(root, "shelves", result->shelves, sizeof(result->shelves));
    stringify_item_codes(root, result->parcel_codes, sizeof(result->parcel_codes));
    if (result->parcel_codes[0] == '\0') {
        stringify_array(root, "parcel_codes", result->parcel_codes, sizeof(result->parcel_codes));
    }
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

static esp_err_t gateway_get_json(const char *path, int *http_status)
{
    memset(s_response, 0, sizeof(s_response));
    esp_err_t err = network_client_http_get(SPS_GATEWAY_HOST, SPS_GATEWAY_PORT, path,
                                             s_response, sizeof(s_response), http_status);
    if (err != ESP_OK) return err;
    return (*http_status >= 200 && *http_status < 300) ? ESP_OK : ESP_FAIL;
}

esp_err_t gateway_client_fetch_qr_session(gateway_qr_session_t *result)
{
    if (result == NULL) return ESP_ERR_INVALID_ARG;
    memset(result, 0, sizeof(*result));
    esp_err_t err = gateway_get_json(SPS_GATEWAY_QR_PATH, &result->http_status);
    if (err != ESP_OK) return err;
    cJSON *root = cJSON_Parse(s_response);
    if (root == NULL) return ESP_ERR_INVALID_RESPONSE;
    copy_json_string(root, "session_id", result->session_id, sizeof(result->session_id));
    copy_json_string(root, "qr_payload", result->qr_payload, sizeof(result->qr_payload));
    result->request_ok = result->qr_payload[0] != '\0';
    cJSON_Delete(root);
    ESP_LOGI(TAG, "QR session received: session_id=%s payload_bytes=%u",
             result->session_id, (unsigned)strlen(result->qr_payload));
    return result->request_ok ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}

esp_err_t gateway_client_poll_auth_result(gateway_access_result_t *result)
{
    if (result == NULL) return ESP_ERR_INVALID_ARG;
    memset(result, 0, sizeof(*result));
    result->pickup_count = -1;
    esp_err_t err = gateway_get_json(SPS_GATEWAY_AUTH_PATH, &result->http_status);
    result->request_ok = err == ESP_OK;
    if (err != ESP_OK) return err;
    parse_gateway_response(s_response, result);
    return ESP_OK;
}

esp_err_t gateway_client_post_access_credential(const char *credential_type,
                                                const char *credential_value,
                                                gateway_access_result_t *result)
{
    if (credential_type == NULL || credential_type[0] == '\0' ||
        credential_value == NULL || credential_value[0] == '\0' || result == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    memset(result, 0, sizeof(*result));
    result->pickup_count = -1;

    cJSON *root = cJSON_CreateObject();
    if (root == NULL) {
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddStringToObject(root, "reader_id", SPS_READER_ID);
    cJSON_AddStringToObject(root, "credential_type", credential_type);
    cJSON_AddStringToObject(root, "credential_value", credential_value);

    char *payload = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (payload == NULL) {
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "POST %s credential_type=%s credential_value=%s",
             SPS_GATEWAY_PATH, credential_type, credential_value);
    memset(s_response, 0, sizeof(s_response));
    esp_err_t err = network_client_http_post_json(
        SPS_GATEWAY_HOST,
        SPS_GATEWAY_PORT,
        SPS_GATEWAY_PATH,
        payload,
        s_response,
        sizeof(s_response),
        &result->http_status);
    cJSON_free(payload);

    result->request_ok = err == ESP_OK && result->http_status >= 200 && result->http_status < 300;
    if (!result->request_ok) {
        ESP_LOGE(TAG, "Gateway request failed, HTTP status=%d, body=%s", result->http_status, s_response);
        return err == ESP_OK ? ESP_FAIL : err;
    }

    parse_gateway_response(s_response, result);
    if (result->access_granted) {
        ESP_LOGI(TAG, "GRANTED display_text=%s", result->display_text);
    } else {
        ESP_LOGI(TAG, "DENIED reason=%s", result->reason);
    }
    return ESP_OK;
}

esp_err_t gateway_client_post_access_card(const char *uid_hex, gateway_access_result_t *result)
{
    return gateway_client_post_access_credential("CARD_UID", uid_hex, result);
}
