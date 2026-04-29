// Fixed libyaml scanner fuzzer
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <yaml.h>

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size == 0) return 0;

    yaml_parser_t parser;
    yaml_token_t token;

    if (!yaml_parser_initialize(&parser))
        return 0;

    yaml_parser_set_input_string(&parser, Data, Size);

    while (yaml_parser_scan(&parser, &token)) {
        if (token.type == YAML_STREAM_END_TOKEN) {
            yaml_token_delete(&token);
            break;
        }
        yaml_token_delete(&token);
    }

    yaml_parser_delete(&parser);
    return 0;
}
