#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "ndpi_api.h"

static void write_dummy_file(const uint8_t *data, size_t size, const char *filename) {
    FILE *file = fopen(filename, "wb");
    if (file) {
        fwrite(data, 1, size, file);
        fclose(file);
    }
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size < 1) return 0;

    struct ndpi_detection_module_struct *detection_module = ndpi_init_detection_module(NULL);
    if (!detection_module) return 0;

    const char *dummy_file = "./dummy_file";
    write_dummy_file(Data, Size, dummy_file);

    for (int i = 0; i < 10; i++) {
        ndpi_load_malicious_ja4_file(detection_module, dummy_file);
    }

    for (int i = 0; i < 10; i++) {
        ndpi_load_tcp_fingerprint_file(detection_module, dummy_file);
    }

    for (int i = 0; i < 10; i++) {
        ndpi_load_malicious_sha1_file(detection_module, dummy_file);
    }

    for (int i = 0; i < 10; i++) {
        ndpi_load_protocol_plugins(detection_module, (char *)dummy_file);
    }

    for (int i = 0; i < 100; i++) {
        ndpi_set_config(detection_module, "proto", "param", "value");
    }

    for (int i = 0; i < 10; i++) {
        ndpi_finalize_initialization(detection_module);
    }

    ndpi_free(detection_module);

    return 0;
}