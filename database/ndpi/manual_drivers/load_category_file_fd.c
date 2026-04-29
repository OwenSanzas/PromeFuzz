// Manual fuzz driver targeting load_category_file_fd.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <ndpi_api.h>
#include <ndpi_typedefs.h>

extern int load_category_file_fd(struct ndpi_detection_module_struct *ndpi_str,
                                 FILE *fd, ndpi_protocol_category_t category_id);

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size == 0 || Size > (1 << 20)) return 0;
    struct ndpi_detection_module_struct *ndpi = ndpi_init_detection_module(NULL);
    if (!ndpi) return 0;
    FILE *fd = fmemopen((void *)Data, Size, "r");
    if (fd) {
        load_category_file_fd(ndpi, fd, NDPI_PROTOCOL_CATEGORY_MEDIA);
        fclose(fd);
    }
    ndpi_exit_detection_module(ndpi);
    return 0;
}
