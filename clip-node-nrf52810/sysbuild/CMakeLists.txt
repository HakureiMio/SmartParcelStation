# SPDX-License-Identifier: Apache-2.0

set(BOARD_ROOT ${APP_DIR} CACHE PATH "SmartParcel clip board root" FORCE)

find_package(Sysbuild REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(sysbuild LANGUAGES)
