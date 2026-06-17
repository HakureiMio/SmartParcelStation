idf_component_register(
    SRCS
        "app_main.c"
        "pn532_reader.c"
        "esp8266_at.c"
        "network_esp8266_at.c"
        "gateway_client.c"
        "display_ui.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_event
        esp_timer
        nvs_flash
        json
)
