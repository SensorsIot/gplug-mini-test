/* Host-tier smoke test: asserts only that the tier compiles and executes
 * without ESP-IDF. It verifies no product requirement. */
#include <stdio.h>

int main(void)
{
#ifdef ESP_PLATFORM
    fprintf(stderr, "host tier built against ESP-IDF\n");
    return 1;
#else
    puts("host tier runs");
    return 0;
#endif
}
