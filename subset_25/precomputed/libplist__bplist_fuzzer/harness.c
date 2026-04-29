// This fuzz driver is generated for library libplist, aiming to fuzz the following functions:
// plist_from_bin at bplist.c:905:13 in plist.h
// plist_free at plist.c:712:6 in plist.h
// plist_from_xml at xplist.c:1637:13 in plist.h
// plist_free at plist.c:712:6 in plist.h
// plist_from_bin at bplist.c:905:13 in plist.h
// plist_to_xml at xplist.c:574:13 in plist.h
// plist_free at plist.c:712:6 in plist.h
// plist_from_json at jplist.c:954:13 in plist.h
// plist_free at plist.c:712:6 in plist.h
// plist_from_openstep at oplist.c:1013:13 in plist.h
// plist_free at plist.c:712:6 in plist.h
// plist_from_bin at bplist.c:905:13 in plist.h
// plist_to_bin at bplist.c:1360:13 in plist.h
// plist_free at plist.c:712:6 in plist.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "plist.h"

static void fuzz_plist_from_bin(const uint8_t *Data, size_t Size) {
    plist_t plist = NULL;
    plist_from_bin((const char *)Data, (uint32_t)Size, &plist);
    if (plist) {
        plist_free(plist);
    }
}

static void fuzz_plist_from_xml(const uint8_t *Data, size_t Size) {
    plist_t plist = NULL;
    plist_from_xml((const char *)Data, (uint32_t)Size, &plist);
    if (plist) {
        plist_free(plist);
    }
}

static void fuzz_plist_to_xml(const uint8_t *Data, size_t Size) {
    plist_t plist = NULL;
    if (plist_from_bin((const char *)Data, (uint32_t)Size, &plist) == PLIST_ERR_SUCCESS) {
        char *xml = NULL;
        uint32_t length = 0;
        plist_to_xml(plist, &xml, &length);
        if (xml) {
            free(xml);
        }
        plist_free(plist);
    }
}

static void fuzz_plist_from_json(const uint8_t *Data, size_t Size) {
    plist_t plist = NULL;
    plist_from_json((const char *)Data, (uint32_t)Size, &plist);
    if (plist) {
        plist_free(plist);
    }
}

static void fuzz_plist_from_openstep(const uint8_t *Data, size_t Size) {
    plist_t plist = NULL;
    plist_from_openstep((const char *)Data, (uint32_t)Size, &plist);
    if (plist) {
        plist_free(plist);
    }
}

static void fuzz_plist_to_bin(const uint8_t *Data, size_t Size) {
    plist_t plist = NULL;
    if (plist_from_bin((const char *)Data, (uint32_t)Size, &plist) == PLIST_ERR_SUCCESS) {
        char *bin = NULL;
        uint32_t length = 0;
        plist_to_bin(plist, &bin, &length);
        if (bin) {
            free(bin);
        }
        plist_free(plist);
    }
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    fuzz_plist_from_bin(Data, Size);
    fuzz_plist_from_xml(Data, Size);
    fuzz_plist_to_xml(Data, Size);
    fuzz_plist_from_json(Data, Size);
    fuzz_plist_from_openstep(Data, Size);
    fuzz_plist_to_bin(Data, Size);
    return 0;
}