// Host test for src/BlackboxDecode.h: feed a log file in 512-byte chunks and print the analyser's JSON parts.
#include "../src/BlackboxDecode.h"
#include <stdio.h>
#include <vector>
int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "usage: bbcheck_test log.bbl [wantLog] [chunk]\n"); return 2; }
    FILE* f = fopen(argv[1], "rb"); if (!f) { perror("open"); return 2; }
    std::vector<uint8_t> d; uint8_t b[4096]; size_t n; while ((n = fread(b, 1, sizeof b, f)) > 0) d.insert(d.end(), b, b + n); fclose(f);
    static BbDec::Decoder dec; static BbAn::Analyser an;
    an.wantLog = argc > 2 ? atoi(argv[2]) : 0;
    const size_t chunk = argc > 3 ? (size_t)atoi(argv[3]) : 512;
    for (size_t i = 0; i < d.size(); i += chunk) { size_t k = d.size() - i; if (k > chunk) k = chunk; dec.feed(&d[i], k, an); if (an.selectedDone) break; }
    dec.finish(an);
    static char out[32768];
    printf("{\"stats\":{\"i\":%u,\"p\":%u,\"s\":%u,\"e\":%u,\"resyncs\":%u,\"bad\":%u,\"logs\":%u,\"bytes\":%u,\"skipped\":%u,\"truncated\":%u}",
           dec.stats.iFrames, dec.stats.pFrames, dec.stats.sFrames, dec.stats.eFrames, dec.stats.resyncs, dec.stats.badFrames, dec.stats.logs, dec.stats.bytes, dec.stats.skipped, dec.stats.truncatedLogs);
    const char* names[] = {"summary", "fly", "gnd", "order", "timeline", "orderFilt", "flight"};
    for (int part = 0; part < 7; part++) { size_t L = an.toJson(part, out, sizeof out); printf(",\"%s\":%s", names[part], L ? out : "null"); fprintf(stderr, "part %d: %zu bytes\n", part, L); }
    printf("}\n");
    return 0;
}
