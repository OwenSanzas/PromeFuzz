// Manual fuzz driver targeting load_protocols_file_fd.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <ndpi_api.h>

extern int load_protocols_file_fd(struct ndpi_detection_module_struct *ndpi_mod, FILE *fd);

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size == 0 || Size > (1 << 20)) return 0;
    struct ndpi_detection_module_struct *ndpi = ndpi_init_detection_module(NULL);
    if (!ndpi) return 0;
    FILE *fd = fmemopen((void *)Data, Size, "r");
    if (fd) {
        load_protocols_file_fd(ndpi, fd);
        fclose(fd);
    }
    ndpi_exit_detection_module(ndpi);
    return 0;
}
