#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <dirent.h>
#include <string>
#include <vector>
#include <fstream>
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        DIR *d = opendir(argv[i]);
        if (d) {
            struct dirent *ent;
            while ((ent = readdir(d)) != nullptr) {
                if (ent->d_name[0] == '.') continue;
                std::string path = std::string(argv[i]) + "/" + ent->d_name;
                std::ifstream ifs(path, std::ios::binary);
                std::vector<uint8_t> buf((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
                LLVMFuzzerTestOneInput(buf.data(), buf.size());
            }
            closedir(d);
        }
    }
    return 0;
}
