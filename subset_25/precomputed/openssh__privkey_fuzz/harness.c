// This fuzz driver is generated for library openssh, aiming to fuzz the following functions:
// sshbuf_from at sshbuf.c:112:1 in sshbuf.h
// sshkey_private_deserialize at sshkey.c:2606:1 in sshkey.h
// sshkey_free at sshkey.c:787:1 in sshkey.h
// sshbuf_free at sshbuf.c:161:1 in sshbuf.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "sshkey.h"
#include "sshbuf.h"

static void dummy_pkcs11_key_free(void) {}
static int dummy_sshsk_sign(void) { return 0; }
static int dummy_pkcs11_sign(void) { return 0; }

void pkcs11_key_free(void) __attribute__((weak, alias("dummy_pkcs11_key_free")));
int sshsk_sign(void) __attribute__((weak, alias("dummy_sshsk_sign")));
int pkcs11_sign(void) __attribute__((weak, alias("dummy_pkcs11_sign")));

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    struct sshbuf *buf = NULL;
    struct sshkey *key = NULL;
    
    if (Size == 0) {
        return 0;
    }

    buf = sshbuf_from(Data, Size);
    if (buf == NULL) {
        return 0;
    }

    if (sshkey_private_deserialize(buf, &key) == 0) {
        sshkey_free(key);
    }

    sshbuf_free(buf);

    return 0;
}