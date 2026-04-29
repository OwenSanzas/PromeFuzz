// This fuzz driver is generated for library jq, aiming to fuzz the following functions:
// jv_parser_new at jv_parse.c:711:19 in jv.h
// jv_parser_set_buf at jv_parse.c:731:6 in jv.h
// jv_parser_next at jv_parse.c:768:4 in jv.h
// jv_is_valid at jv.h:52:12 in jv.h
// jv_free at jv.c:1966:6 in jv.h
// jv_free at jv.c:1966:6 in jv.h
// jv_parser_free at jv_parse.c:718:6 in jv.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include "jv.h"

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size == 0) return 0;

    // Initialize the parser
    jv_parser* parser = jv_parser_new(0);
    if (!parser) return 0;

    // Set buffer with the input data
    jv_parser_set_buf(parser, (const char*)Data, (int)Size, 0);

    // Parse and process the input
    jv value = jv_parser_next(parser);
    if (jv_is_valid(value)) {
        // Free the valid JSON value
        jv_free(value);
    } else {
        // Free the invalid JSON value
        jv_free(value);
    }

    // Clean up parser resources
    jv_parser_free(parser);

    return 0;
}