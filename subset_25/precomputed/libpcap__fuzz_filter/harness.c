// This fuzz driver is generated for library libpcap, aiming to fuzz the following functions:
// pcap_strerror at pcap.c:3784:1 in pcap.h
// pcap_open_offline at savefile.c:388:1 in pcap.h
// pcap_datalink_name_to_val at pcap.c:3415:1 in pcap.h
// pcap_open_dead at pcap.c:4696:1 in pcap.h
// pcap_close at pcap.c:4323:1 in pcap.h
// pcap_compile at gencode.c:1302:1 in pcap.h
// pcap_freecode at gencode.c:1493:1 in pcap.h
// pcap_close at pcap.c:4323:1 in pcap.h
// pcap_close at pcap.c:4323:1 in pcap.h
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <pcap.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void write_dummy_file(const uint8_t *Data, size_t Size) {
    FILE *file = fopen("./dummy_file", "wb");
    if (file) {
        fwrite(Data, 1, Size, file);
        fclose(file);
    }
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    if (Size < 1) return 0;

    // Step 1: pcap_strerror
    int error_code = Data[0];
    const char *error_msg = pcap_strerror(error_code);
    if (error_msg) {
        // Use the error message somehow to avoid compiler optimizations
        volatile size_t len = strlen(error_msg);
        (void)len;
    }

    // Step 2: pcap_open_offline
    write_dummy_file(Data, Size);
    char errbuf[PCAP_ERRBUF_SIZE];
    pcap_t *pcap = pcap_open_offline("./dummy_file", errbuf);
    if (!pcap) {
        return 0;
    }

    // Step 3: pcap_datalink_name_to_val
    int datalink_val = pcap_datalink_name_to_val((const char *)Data);
    (void)datalink_val;

    // Step 4: pcap_open_dead
    pcap_t *dead_pcap = pcap_open_dead(DLT_EN10MB, 65535);
    if (!dead_pcap) {
        pcap_close(pcap);
        return 0;
    }

    // Step 5: pcap_compile
    struct bpf_program fp;
    int optimize = 0;
    bpf_u_int32 netmask = 0xFFFFFF00;
    int compile_result = pcap_compile(dead_pcap, &fp, (const char *)Data, optimize, netmask);
    if (compile_result == 0) {
        pcap_freecode(&fp);
    }

    // Cleanup
    pcap_close(dead_pcap);
    pcap_close(pcap);

    return 0;
}