#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "ndpi_api.h"

static void write_dummy_file(const uint8_t *Data, size_t Size) {
    FILE *file = fopen("./dummy_file", "wb");
    if (file) {
        fwrite(Data, 1, Size, file);
        fclose(file);
    }
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    struct ndpi_detection_module_struct *ndpi_struct;
    struct ndpi_flow_struct *flow;
    struct ndpi_flow_input_info *input_info;
    ndpi_protocol protocol;
    ndpi_serializer serializer;
    unsigned char *packet;
    unsigned short packetlen;
    u_int64_t packet_time_ms;

    // Initialize global context
    struct ndpi_global_context *g_ctx = NULL; // Assuming global context is not required for this test

    // Initialize ndpi_struct using an appropriate function
    ndpi_struct = ndpi_init_detection_module(g_ctx);
    if (!ndpi_struct) {
        return 0;
    }

    // Allocate memory for flow and input_info
    flow = (struct ndpi_flow_struct *)malloc(sizeof(struct ndpi_flow_struct));
    input_info = (struct ndpi_flow_input_info *)malloc(sizeof(struct ndpi_flow_input_info));

    if (!flow || !input_info) {
        ndpi_exit_detection_module(ndpi_struct);
        free(flow);
        free(input_info);
        return 0;
    }

    // Initialize flow and input_info with dummy values
    memset(flow, 0, sizeof(*flow));
    memset(input_info, 0, sizeof(*input_info));
    packet = (unsigned char *)Data;
    packetlen = (unsigned short)(Size > 65535 ? 65535 : Size);
    packet_time_ms = 0;

    // Initialize serializer with dummy format
    ndpi_serialization_format fmt = ndpi_serialization_format_json;
    ndpi_init_serializer(&serializer, fmt);
    ndpi_init_serializer(&serializer, fmt);

    // Process packet
    protocol = ndpi_detection_process_packet(ndpi_struct, flow, packet, packetlen, packet_time_ms, input_info);

    // Give up detection
    ndpi_detection_giveup(ndpi_struct, flow);

    // Reset serializer
    ndpi_reset_serializer(&serializer);
    ndpi_reset_serializer(&serializer);

    // Serialize DPI to JSON
    ndpi_dpi2json(ndpi_struct, flow, protocol, &serializer);
    ndpi_dpi2json(ndpi_struct, flow, protocol, &serializer);

    // Free flow data
    ndpi_free_flow_data(flow);

    // Free allocated structures
    ndpi_exit_detection_module(ndpi_struct);
    free(flow);
    free(input_info);

    return 0;
}