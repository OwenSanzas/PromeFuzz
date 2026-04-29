#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <dirent.h>
#include <string.h>
extern int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        DIR *d = opendir(argv[i]);
        if (d) {
            struct dirent *ent;
            while ((ent = readdir(d)) != NULL) {
                if (ent->d_name[0] == '.') continue;
                char path[4096];
                snprintf(path, sizeof(path), "%s/%s", argv[i], ent->d_name);
                FILE *f = fopen(path, "rb");
                if (!f) continue;
                fseek(f, 0, SEEK_END);
                long len = ftell(f);
                fseek(f, 0, SEEK_SET);
                uint8_t *buf = (uint8_t *)malloc(len);
                fread(buf, 1, len, f);
                fclose(f);
                LLVMFuzzerTestOneInput(buf, len);
                free(buf);
            }
            closedir(d);
        } else {
            FILE *f = fopen(argv[i], "rb");
            if (!f) continue;
            fseek(f, 0, SEEK_END);
            long len = ftell(f);
            fseek(f, 0, SEEK_SET);
            uint8_t *buf = (uint8_t *)malloc(len);
            fread(buf, 1, len, f);
            fclose(f);
            LLVMFuzzerTestOneInput(buf, len);
            free(buf);
        }
    }
    return 0;
}
