cmake_minimum_required(VERSION 3.20.0)

list(APPEND BOARD_ROOT ${CMAKE_CURRENT_SOURCE_DIR})

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(clip_node_nrf52810)

target_sources(app PRIVATE
  src/main.c
  src/clip_state.c
  src/ble_clip_service.c
  src/led_rgb.c
  src/buzzer.c
  src/remove_sensor.c
  src/battery_monitor.c
  src/clip_protocol.c
)
