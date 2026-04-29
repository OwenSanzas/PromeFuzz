// This fuzz driver is generated for library cjson, aiming to fuzz the following functions:
// cJSON_Parse at cJSON.c:1227:23 in cJSON.h
// cJSON_GetErrorPtr at cJSON.c:94:28 in cJSON.h
// cJSON_GetObjectItemCaseSensitive at cJSON.c:1988:23 in cJSON.h
// cJSON_IsString at cJSON.c:3032:26 in cJSON.h
// cJSON_GetObjectItemCaseSensitive at cJSON.c:1988:23 in cJSON.h
// cJSON_GetObjectItemCaseSensitive at cJSON.c:1988:23 in cJSON.h
// cJSON_GetObjectItemCaseSensitive at cJSON.c:1988:23 in cJSON.h
// cJSON_IsNumber at cJSON.c:3022:26 in cJSON.h
// cJSON_IsNumber at cJSON.c:3022:26 in cJSON.h
// cJSON_Delete at cJSON.c:253:20 in cJSON.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include "cJSON.h"

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size == 0) {
        return 0;
    }

    // Ensure the input is null-terminated for cJSON_Parse
    char *json_data = (char *)malloc(Size + 1);
    if (json_data == NULL) {
        return 0;
    }
    memcpy(json_data, Data, Size);
    json_data[Size] = '\0';

    // Parse the JSON data
    cJSON *json = cJSON_Parse(json_data);
    free(json_data);

    if (json == NULL) {
        // If parsing fails, get the error pointer
        const char *error_ptr = cJSON_GetErrorPtr();
        if (error_ptr != NULL) {
            // Handle error (for debugging purposes, can be logged)
        }
        return 0;
    }

    // Get an object item case sensitively
    cJSON *item = cJSON_GetObjectItemCaseSensitive(json, "key1");
    if (item != NULL) {
        // Check if the item is a string
        cJSON_IsString(item);
    }

    // Get another object item case sensitively
    cJSON *item2 = cJSON_GetObjectItemCaseSensitive(json, "key2");
    if (item2 != NULL) {
        // Get another object item case sensitively
        cJSON *item3 = cJSON_GetObjectItemCaseSensitive(item2, "key3");
        if (item3 != NULL) {
            // Get another object item case sensitively
            cJSON *item4 = cJSON_GetObjectItemCaseSensitive(item3, "key4");
            if (item4 != NULL) {
                // Check if the item is a number
                cJSON_IsNumber(item4);
            }
        }

        // Check if the item is a number
        cJSON_IsNumber(item2);
    }

    // Clean up and delete the JSON object
    cJSON_Delete(json);

    return 0;
}