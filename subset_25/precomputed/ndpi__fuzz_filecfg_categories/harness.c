#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>
#include "ndpi_api.h"

static void write_dummy_file(const char *path, const uint8_t *data, size_t size) {
    FILE *file = fopen(path, "wb");
    if (file) {
        fwrite(data, 1, size, file);
        fclose(file);
    }
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    struct ndpi_detection_module_struct *ndpi_mod = ndpi_init_detection_module(NULL);
    if (!ndpi_mod) return 0;

    // Write the dummy file for domain suffixes
    write_dummy_file("./dummy_file", Data, Size);

    // Load domain suffixes
    int load_result = ndpi_load_domain_suffixes(ndpi_mod, "./dummy_file");
    if (load_result != 0) {
        ndpi_exit_detection_module(ndpi_mod);
        return 0;
    }

    // Allocate domain classify structure
    ndpi_domain_classify *domain_classify = ndpi_domain_classify_alloc();
    if (!domain_classify) {
        ndpi_exit_detection_module(ndpi_mod);
        return 0;
    }

    // Add domain with class id
    uint32_t class_id = 1;
    char domain[] = "example.com";
    ndpi_domain_classify_add(ndpi_mod, domain_classify, class_id, domain);

    // Add domains from file
    ndpi_domain_classify_add_domains(ndpi_mod, domain_classify, class_id, "./dummy_file");

    // Classify a hostname
    uint64_t classified_id = 0;
    const char *hostname = "sub.example.com";
    ndpi_domain_classify_hostname(ndpi_mod, domain_classify, &classified_id, hostname);

    // Classify another hostname
    const char *hostname2 = "another.example.com";
    ndpi_domain_classify_hostname(ndpi_mod, domain_classify, &classified_id, hostname2);

    // Get the size of the domain classify structure
    ndpi_domain_classify_size(domain_classify);

    // Free the domain classify structure
    ndpi_domain_classify_free(domain_classify);

    ndpi_exit_detection_module(ndpi_mod);
    return 0;
}