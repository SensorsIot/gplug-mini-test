#pragma once

#include <stdint.h>

/* Mirror every log line to a UDP target (FSD §12). Serial output is unchanged.
 * udp_log_init() installs the hook; lines are dropped until a target is set. */
void udp_log_init(void);

/* ipv4 in network byte order. Called once the STA has an IP (FR-LOG-01). */
void udp_log_set_target(uint32_t ipv4, uint16_t port);
