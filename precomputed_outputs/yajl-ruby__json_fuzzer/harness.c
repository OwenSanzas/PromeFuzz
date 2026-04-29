// This fuzz driver is generated for library yajl_ruby, aiming to fuzz the following functions:
// yajl_alloc at yajl.c:67:1 in yajl_parse.h
// yajl_parse at yajl.c:135:1 in yajl_parse.h
// yajl_status_to_string at yajl.c:43:1 in yajl_parse.h
// yajl_parse_complete at yajl.c:145:1 in yajl_parse.h
// yajl_status_to_string at yajl.c:43:1 in yajl_parse.h
// yajl_reset_parser at yajl.c:119:1 in yajl_parse.h
// yajl_get_bytes_consumed at yajl.c:166:1 in yajl_parse.h
// yajl_free at yajl.c:125:1 in yajl_parse.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "yajl_parse.h"

// Dummy callback functions
static int yajl_null(void *ctx) { return 1; }
static int yajl_boolean(void *ctx, int boolVal) { return 1; }
static int yajl_integer(void *ctx, long long integerVal) { return 1; }
static int yajl_double(void *ctx, double doubleVal) { return 1; }
static int yajl_number(void *ctx, const char *numberVal, size_t numberLen) { return 1; }
static int yajl_string(void *ctx, const unsigned char *stringVal, size_t stringLen) { return 1; }
static int yajl_start_map(void *ctx) { return 1; }
static int yajl_map_key(void *ctx, const unsigned char *key, size_t stringLen) { return 1; }
static int yajl_end_map(void *ctx) { return 1; }
static int yajl_start_array(void *ctx) { return 1; }
static int yajl_end_array(void *ctx) { return 1; }

static yajl_handle initialize_parser() {
    yajl_callbacks callbacks = {
        yajl_null,
        yajl_boolean,
        yajl_integer,
        yajl_double,
        yajl_number,
        yajl_string,
        yajl_start_map,
        yajl_map_key,
        yajl_end_map,
        yajl_start_array,
        yajl_end_array
    };
    
    yajl_alloc_funcs allocFuncs = {0}; // Use default allocation functions
    return yajl_alloc(&callbacks, NULL, &allocFuncs, NULL);
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size == 0) return 0;

    yajl_handle hand = initialize_parser();
    if (!hand) return 0;

    yajl_status status = yajl_parse(hand, Data, Size);
    
    // Check the status and print error if any
    if (status != yajl_status_ok) {
        const char *errorStr = yajl_status_to_string(status);
        fprintf(stderr, "Parse Error: %s\n", errorStr);
    }

    // Complete the parsing
    status = yajl_parse_complete(hand);
    if (status != yajl_status_ok) {
        const char *errorStr = yajl_status_to_string(status);
        fprintf(stderr, "Parse Complete Error: %s\n", errorStr);
    }

    // Reset the parser to explore more states
    yajl_reset_parser(hand);

    // Get bytes consumed for debugging purposes
    unsigned int bytesConsumed = yajl_get_bytes_consumed(hand);
    fprintf(stderr, "Bytes Consumed: %u\n", bytesConsumed);

    yajl_free(hand);
    return 0;
}