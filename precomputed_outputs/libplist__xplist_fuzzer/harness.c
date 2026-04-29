// This fuzz driver is generated for library libplist, aiming to fuzz the following functions:
// plist_from_xml at xplist.c:1637:13 in plist.h
// plist_to_json at jplist.c:495:13 in plist.h
// plist_mem_free at plist.c:720:6 in plist.h
// plist_to_openstep at oplist.c:551:13 in plist.h
// plist_mem_free at plist.c:720:6 in plist.h
// plist_to_xml at xplist.c:574:13 in plist.h
// plist_mem_free at plist.c:720:6 in plist.h
// plist_from_bin at bplist.c:905:13 in plist.h
// plist_free at plist.c:712:6 in plist.h
// plist_from_xml at xplist.c:1637:13 in plist.h
// plist_free at plist.c:712:6 in plist.h
// plist_from_openstep at oplist.c:1013:13 in plist.h
// plist_free at plist.c:712:6 in plist.h
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

static plist_t create_dummy_plist() {
    plist_t plist = NULL;
    plist_from_xml("<plist version=\"1.0\"><dict><key>dummy</key><string>value</string></dict></plist>", 81, &plist);
    return plist;
}

static void fuzz_plist_to_json(plist_t plist) {
    char *plist_json = NULL;
    uint32_t length = 0;
    int prettify = 1;
    plist_err_t err = plist_to_json(plist, &plist_json, &length, prettify);
    if (err == PLIST_ERR_SUCCESS) {
        plist_mem_free(plist_json);
    }
}

static void fuzz_plist_to_openstep(plist_t plist) {
    char *plist_openstep = NULL;
    uint32_t length = 0;
    int prettify = 0;
    plist_err_t err = plist_to_openstep(plist, &plist_openstep, &length, prettify);
    if (err == PLIST_ERR_SUCCESS) {
        plist_mem_free(plist_openstep);
    }
}

static void fuzz_plist_to_xml(plist_t plist) {
    char *plist_xml = NULL;
    uint32_t length = 0;
    plist_err_t err = plist_to_xml(plist, &plist_xml, &length);
    if (err == PLIST_ERR_SUCCESS) {
        plist_mem_free(plist_xml);
    }
}

static void fuzz_plist_from_bin(const uint8_t *Data, size_t Size) {
    plist_t plist = NULL;
    plist_err_t err = plist_from_bin((const char *)Data, (uint32_t)Size, &plist);
    if (err == PLIST_ERR_SUCCESS) {
        plist_free(plist);
    }
}

static void fuzz_plist_from_xml(const uint8_t *Data, size_t Size) {
    plist_t plist = NULL;
    plist_err_t err = plist_from_xml((const char *)Data, (uint32_t)Size, &plist);
    if (err == PLIST_ERR_SUCCESS) {
        plist_free(plist);
    }
}

static void fuzz_plist_from_openstep(const uint8_t *Data, size_t Size) {
    plist_t plist = NULL;
    plist_err_t err = plist_from_openstep((const char *)Data, (uint32_t)Size, &plist);
    if (err == PLIST_ERR_SUCCESS) {
        plist_free(plist);
    }
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    plist_t dummy_plist = create_dummy_plist();
    if (!dummy_plist) {
        return 0;
    }

    fuzz_plist_to_json(dummy_plist);
    fuzz_plist_to_openstep(dummy_plist);
    fuzz_plist_to_xml(dummy_plist);

    fuzz_plist_from_bin(Data, Size);
    fuzz_plist_from_xml(Data, Size);
    fuzz_plist_from_openstep(Data, Size);

    plist_free(dummy_plist);
    return 0;
}