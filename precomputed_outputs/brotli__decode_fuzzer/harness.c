// This fuzz driver is generated for library brotli, aiming to fuzz the following functions:
// BrotliEncoderCreateInstance at encode.c:762:21 in encode.h
// BrotliDecoderCreateInstance at decode.c:79:21 in decode.h
// BrotliEncoderDestroyInstance at encode.c:803:6 in encode.h
// BrotliDecoderDestroyInstance at decode.c:108:6 in decode.h
// BrotliEncoderMaxCompressedSize at encode.c:1227:8 in encode.h
// BrotliEncoderCompressStream at encode.c:1610:13 in encode.h
// BrotliEncoderTakeOutput at encode.c:1709:16 in encode.h
// BrotliDecoderDecompressStream at decode.c:2422:21 in decode.h
// BrotliDecoderTakeOutput at decode.c:2916:16 in decode.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "decode.h"
#include "encode.h"

static BrotliEncoderState* createEncoderState() {
    BrotliEncoderState* state = BrotliEncoderCreateInstance(NULL, NULL, NULL);
    if (!state) {
        fprintf(stderr, "Failed to create BrotliEncoderState\n");
        exit(1);
    }
    return state;
}

static BrotliDecoderState* createDecoderState() {
    BrotliDecoderState* state = BrotliDecoderCreateInstance(NULL, NULL, NULL);
    if (!state) {
        fprintf(stderr, "Failed to create BrotliDecoderState\n");
        exit(1);
    }
    return state;
}

static void cleanupEncoderState(BrotliEncoderState* state) {
    BrotliEncoderDestroyInstance(state);
}

static void cleanupDecoderState(BrotliDecoderState* state) {
    BrotliDecoderDestroyInstance(state);
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    // Fuzz BrotliEncoderMaxCompressedSize
    size_t max_compressed_size = BrotliEncoderMaxCompressedSize(Size);

    // Fuzz BrotliEncoderCompressStream
    BrotliEncoderState* encoder_state = createEncoderState();
    size_t available_in = Size;
    const uint8_t* next_in = Data;
    size_t available_out = max_compressed_size;
    uint8_t* compressed_data = (uint8_t*)malloc(max_compressed_size);
    uint8_t* next_out = compressed_data;
    size_t total_out = 0;
    BrotliEncoderCompressStream(encoder_state, BROTLI_OPERATION_FINISH, &available_in, &next_in, &available_out, &next_out, &total_out);

    // Fuzz BrotliEncoderTakeOutput
    size_t output_size = 0;
    const uint8_t* output_data = BrotliEncoderTakeOutput(encoder_state, &output_size);

    // Fuzz BrotliDecoderDecompressStream
    BrotliDecoderState* decoder_state = createDecoderState();
    size_t available_in_dec = total_out;
    const uint8_t* next_in_dec = compressed_data;
    size_t available_out_dec = Size;
    uint8_t* decompressed_data = (uint8_t*)malloc(Size);
    uint8_t* next_out_dec = decompressed_data;
    size_t total_out_dec = 0;
    BrotliDecoderDecompressStream(decoder_state, &available_in_dec, &next_in_dec, &available_out_dec, &next_out_dec, &total_out_dec);

    // Fuzz BrotliDecoderTakeOutput
    size_t output_size_dec = 0;
    const uint8_t* output_data_dec = BrotliDecoderTakeOutput(decoder_state, &output_size_dec);

    // Cleanup
    cleanupEncoderState(encoder_state);
    cleanupDecoderState(decoder_state);
    free(compressed_data);
    free(decompressed_data);

    return 0;
}