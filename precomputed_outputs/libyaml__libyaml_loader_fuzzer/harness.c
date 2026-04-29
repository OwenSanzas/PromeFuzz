// This fuzz driver is generated for library libyaml, aiming to fuzz the following functions:
// yaml_parser_delete at api.c:220:1 in yaml.h
// yaml_document_delete at api.c:1123:1 in yaml.h
// yaml_parser_set_encoding at api.c:342:1 in yaml.h
// yaml_parser_set_input_string at api.c:289:1 in yaml.h
// yaml_parser_load at loader.c:87:1 in yaml.h
// yaml_parser_initialize at api.c:177:1 in yaml.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <yaml.h>

static void initialize_parser(yaml_parser_t *parser) {
    yaml_parser_initialize(parser);
}

static void cleanup_parser(yaml_parser_t *parser) {
    yaml_parser_delete(parser);
}

static void cleanup_document(yaml_document_t *document) {
    yaml_document_delete(document);
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size == 0) return 0;

    yaml_parser_t parser;
    yaml_document_t document;
    FILE *file = fopen("./dummy_file", "wb");
    if (!file) return 0;

    fwrite(Data, 1, Size, file);
    fclose(file);

    initialize_parser(&parser);

    // Use a portion of the input data to set encoding
    yaml_encoding_t encoding = (yaml_encoding_t)(Data[0] % 4);
    yaml_parser_set_encoding(&parser, encoding);

    // Set input string with the data
    yaml_parser_set_input_string(&parser, Data, Size);

    // Try loading the document
    if (yaml_parser_load(&parser, &document)) {
        cleanup_document(&document);
    }

    // Clean up
    cleanup_parser(&parser);

    return 0;
}