// This fuzz driver is generated for library zlib, aiming to fuzz the following functions:
// compressBound at compress.c:96:15 in zlib.h
// compress_z at compress.c:77:13 in zlib.h
// uncompress2_z at uncompr.c:29:13 in zlib.h
// uncompress_z at uncompr.c:92:13 in zlib.h
// compressBound at compress.c:96:15 in zlib.h
// compress2_z at compress.c:24:13 in zlib.h
// uncompress2 at uncompr.c:83:13 in zlib.h
// compressBound at compress.c:96:15 in zlib.h
// compress2 at compress.c:67:13 in zlib.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "zlib.h"

static void fuzz_compress_z(const uint8_t *Data, size_t Size) {
    z_size_t destLen = compressBound(Size);
    Bytef *dest = (Bytef *)malloc(destLen);
    if (!dest) return;

    int ret = compress_z(dest, &destLen, Data, Size);
    if (ret != Z_OK) {
        // Handle error if needed
    }

    free(dest);
}

static void fuzz_uncompress2_z(const uint8_t *Data, size_t Size) {
    z_size_t destLen = Size * 2; // Arbitrary size for decompression buffer
    Bytef *dest = (Bytef *)malloc(destLen);
    if (!dest) return;

    int ret = uncompress2_z(dest, &destLen, Data, &Size);
    if (ret != Z_OK) {
        // Handle error if needed
    }

    free(dest);
}

static void fuzz_uncompress_z(const uint8_t *Data, size_t Size) {
    z_size_t destLen = Size * 2; // Arbitrary size for decompression buffer
    Bytef *dest = (Bytef *)malloc(destLen);
    if (!dest) return;

    int ret = uncompress_z(dest, &destLen, Data, Size);
    if (ret != Z_OK) {
        // Handle error if needed
    }

    free(dest);
}

static void fuzz_compress2_z(const uint8_t *Data, size_t Size) {
    z_size_t destLen = compressBound(Size);
    Bytef *dest = (Bytef *)malloc(destLen);
    if (!dest) return;

    int level = Z_BEST_COMPRESSION; // Use best compression level
    int ret = compress2_z(dest, &destLen, Data, Size, level);
    if (ret != Z_OK) {
        // Handle error if needed
    }

    free(dest);
}

static void fuzz_uncompress2(const uint8_t *Data, size_t Size) {
    uLongf destLen = Size * 2; // Arbitrary size for decompression buffer
    Bytef *dest = (Bytef *)malloc(destLen);
    if (!dest) return;

    uLong sourceLen = Size;
    int ret = uncompress2(dest, &destLen, Data, &sourceLen);
    if (ret != Z_OK) {
        // Handle error if needed
    }

    free(dest);
}

static void fuzz_compress2(const uint8_t *Data, size_t Size) {
    uLongf destLen = compressBound(Size);
    Bytef *dest = (Bytef *)malloc(destLen);
    if (!dest) return;

    int level = Z_BEST_COMPRESSION; // Use best compression level
    int ret = compress2(dest, &destLen, Data, Size, level);
    if (ret != Z_OK) {
        // Handle error if needed
    }

    free(dest);
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    fuzz_compress_z(Data, Size);
    fuzz_uncompress2_z(Data, Size);
    fuzz_uncompress_z(Data, Size);
    fuzz_compress2_z(Data, Size);
    fuzz_uncompress2(Data, Size);
    fuzz_compress2(Data, Size);
    return 0;
}