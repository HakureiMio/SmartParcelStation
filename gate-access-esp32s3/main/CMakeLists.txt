idf_component_register(
    SRCS
        "app_main.c"
        "wifi_client.c"
        "pn532_reader.c"
        "gateway_client.c"
    INCLUDE_DIRS "."
    REQUIRES
        esp_wifi
        esp_event
        nvs_flash
        esp_http_client
        json
        driver
)
