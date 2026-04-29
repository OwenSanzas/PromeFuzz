// This fuzz driver is generated for library zopfli, aiming to fuzz the following functions:
// ZopfliInitOptions at util.c:28:6 in zopfli.h
// ZopfliCompress at zopfli_lib.c:28:6 in zopfli.h
// ZopfliInitOptions at util.c:28:6 in zopfli.h
// ZopfliDeflate at deflate.c:908:6 in deflate.h
// ZopfliInitOptions at util.c:28:6 in zopfli.h
// ZopfliDeflatePart at deflate.c:811:6 in deflate.h
// ZopfliCalculateBlockSize at deflate.c:584:8 in deflate.h
// ZopfliCalculateBlockSizeAutoType at deflate.c:610:8 in deflate.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "zopfli.h"
#include "deflate.h"

static void FuzzZopfliCompress(const uint8_t *Data, size_t Size) {
  ZopfliOptions options;
  ZopfliInitOptions(&options);

  unsigned char *out = NULL;
  size_t outsize = 0;

  ZopfliCompress(&options, ZOPFLI_FORMAT_GZIP, Data, Size, &out, &outsize);

  free(out);
}

static void FuzzZopfliDeflate(const uint8_t *Data, size_t Size) {
  ZopfliOptions options;
  ZopfliInitOptions(&options);

  unsigned char *out = NULL;
  size_t outsize = 0;
  unsigned char bp = 0;

  ZopfliDeflate(&options, 2, 1, Data, Size, &bp, &out, &outsize);

  free(out);
}

static void FuzzZopfliDeflatePart(const uint8_t *Data, size_t Size) {
  if (Size < 2) return;

  ZopfliOptions options;
  ZopfliInitOptions(&options);

  unsigned char *out = NULL;
  size_t outsize = 0;
  unsigned char bp = 0;

  size_t instart = 0;
  size_t inend = Size > 1 ? Size - 1 : Size;

  ZopfliDeflatePart(&options, 2, 1, Data, instart, inend, &bp, &out, &outsize);

  free(out);
}

static void FuzzZopfliCalculateBlockSize(const uint8_t *Data, size_t Size) {
  if (Size < sizeof(ZopfliLZ77Store)) return;

  ZopfliLZ77Store lz77;
  memset(&lz77, 0, sizeof(ZopfliLZ77Store));

  double block_size = ZopfliCalculateBlockSize(&lz77, 0, Size, 2);
  (void)block_size;
}

static void FuzzZopfliCalculateBlockSizeAutoType(const uint8_t *Data, size_t Size) {
  if (Size < sizeof(ZopfliLZ77Store)) return;

  ZopfliLZ77Store lz77;
  memset(&lz77, 0, sizeof(ZopfliLZ77Store));

  double block_size = ZopfliCalculateBlockSizeAutoType(&lz77, 0, Size);
  (void)block_size;
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
  FuzzZopfliCompress(Data, Size);
  FuzzZopfliDeflate(Data, Size);
  FuzzZopfliDeflatePart(Data, Size);
  FuzzZopfliCalculateBlockSize(Data, Size);
  FuzzZopfliCalculateBlockSizeAutoType(Data, Size);

  return 0;
}