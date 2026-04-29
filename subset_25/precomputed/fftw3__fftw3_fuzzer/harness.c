// This fuzz driver is generated for library fftw3, aiming to fuzz the following functions:
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
// fftw_execute at execute.c:23:6 in fftw3.h
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <fftw3.h>

static void fuzz_fftw_execute_dft(const uint8_t *Data, size_t Size) {
    if (Size < 2 * sizeof(fftw_complex)) return;

    fftw_complex *in = (fftw_complex *)malloc(sizeof(fftw_complex));
    fftw_complex *out = (fftw_complex *)malloc(sizeof(fftw_complex));

    if (!in || !out) {
        free(in);
        free(out);
        return;
    }

    memcpy(in, Data, sizeof(fftw_complex));
    memcpy(out, Data + sizeof(fftw_complex), sizeof(fftw_complex));

    fftw_plan p = fftw_plan_dft_1d(1, in, out, FFTW_FORWARD, FFTW_ESTIMATE);
    if (p) {
        fftw_execute_dft(p, in, out);
        fftw_destroy_plan(p);
    }

    free(in);
    free(out);
}

static void fuzz_fftw_sprint_plan(const uint8_t *Data, size_t Size) {
    fftw_complex *in = (fftw_complex *)malloc(sizeof(fftw_complex));
    fftw_complex *out = (fftw_complex *)malloc(sizeof(fftw_complex));

    if (!in || !out) {
        free(in);
        free(out);
        return;
    }

    fftw_plan p = fftw_plan_dft_1d(1, in, out, FFTW_FORWARD, FFTW_ESTIMATE);
    if (p) {
        char *str = fftw_sprint_plan(p);
        if (str) {
            free(str);
        }
        fftw_destroy_plan(p);
    }

    free(in);
    free(out);
}

static void fuzz_fftw_print_plan(const uint8_t *Data, size_t Size) {
    fftw_complex *in = (fftw_complex *)malloc(sizeof(fftw_complex));
    fftw_complex *out = (fftw_complex *)malloc(sizeof(fftw_complex));

    if (!in || !out) {
        free(in);
        free(out);
        return;
    }

    fftw_plan p = fftw_plan_dft_1d(1, in, out, FFTW_FORWARD, FFTW_ESTIMATE);
    if (p) {
        fftw_print_plan(p);
        fftw_destroy_plan(p);
    }

    free(in);
    free(out);
}

static void fuzz_fftw_destroy_plan(const uint8_t *Data, size_t Size) {
    fftw_complex *in = (fftw_complex *)malloc(sizeof(fftw_complex));
    fftw_complex *out = (fftw_complex *)malloc(sizeof(fftw_complex));

    if (!in || !out) {
        free(in);
        free(out);
        return;
    }

    fftw_plan p = fftw_plan_dft_1d(1, in, out, FFTW_FORWARD, FFTW_ESTIMATE);
    if (p) {
        fftw_destroy_plan(p);
    }

    free(in);
    free(out);
}

static void fuzz_fftw_export_wisdom_to_string(const uint8_t *Data, size_t Size) {
    char *wisdom = fftw_export_wisdom_to_string();

    if (wisdom) {
        free(wisdom);
    }
}

static void fuzz_fftw_fprint_plan(const uint8_t *Data, size_t Size) {
    fftw_complex *in = (fftw_complex *)malloc(sizeof(fftw_complex));
    fftw_complex *out = (fftw_complex *)malloc(sizeof(fftw_complex));

    if (!in || !out) {
        free(in);
        free(out);
        return;
    }

    fftw_plan p = fftw_plan_dft_1d(1, in, out, FFTW_FORWARD, FFTW_ESTIMATE);
    if (p) {
        FILE *file = fopen("./dummy_file", "w");
        if (file) {
            fftw_fprint_plan(p, file);
            fclose(file);
        }
        fftw_destroy_plan(p);
    }

    free(in);
    free(out);
}

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    fuzz_fftw_execute_dft(Data, Size);
    fuzz_fftw_sprint_plan(Data, Size);
    fuzz_fftw_print_plan(Data, Size);
    fuzz_fftw_destroy_plan(Data, Size);
    fuzz_fftw_export_wisdom_to_string(Data, Size);
    fuzz_fftw_fprint_plan(Data, Size);
    return 0;
}