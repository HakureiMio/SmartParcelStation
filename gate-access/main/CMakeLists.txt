idf_component_register(
    SRCS
        "app_main.c"
        "pn532_reader.c"
        "pn532_diag.c"
        "esp8266_at.c"
        "network_esp8266_at.c"
        "gateway_client.c"
        "display_ui.c"
        "display_board_ctrl.c"
        "touch_test.c"
        "qrcodegen.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_driver_gpio
        esp_driver_i2c
        esp_driver_uart
        esp_event
        esp_hw_support
        esp_lcd
        esp_timer
        nvs_flash
        espressif__cjson
)

# Upstream qrcodegen contains defensive enum lower-bound assertions that some
# embedded GCC versions diagnose as always true.
set_source_files_properties(qrcodegen.c PROPERTIES COMPILE_OPTIONS "-Wno-type-limits")
