# Only what the code includes today. A component added before its code exists
# breaks configuration with a misleading error (docs/Method/project/architecture.md).
idf_component_register(
    SRCS "app_main.c" "udp_log.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES lwip freertos log
)
