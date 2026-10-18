// The panel's rows (screen 1.11.94): the page, with our layer over one or two stretches of each row the layer covers.
// Until 1.11.94 the layer was one rectangle. The help pages now have two buttons of ours on the same rows - Animation top
// left, Fix problems top right - with the page's own title between them, which must stay in view: two stretches.
// Host-tested (hmi/test_film/test_film.cpp).
#pragma once
#include <cstdint>
#include <cstring>
namespace ldrclayer {
// One row, x .. x+w: from the page, except the columns [a1, b1) and [a2, b2) from the layer (a stretch with b <= a is none;
// the second lies right of the first). dst, page and top all point at the row's first pixel.
inline void composeRow(uint16_t *dst, const uint16_t *page, const uint16_t *top, int x, int w, int a1, int b1, int a2, int b2) {
    int cur = x; const int end = x + w;
    auto part = [&](int a0, int b0) {
        const int a = a0 > cur ? a0 : cur, b = b0 < end ? b0 : end;
        if (b <= a) return;
        if (a > cur) memcpy(dst + cur, page + cur, (size_t) (a - cur) * 2);
        memcpy(dst + a, top + a, (size_t) (b - a) * 2);
        cur = b;
    };
    part(a1, b1); part(a2, b2);
    if (end > cur) memcpy(dst + cur, page + cur, (size_t) (end - cur) * 2);
}
// Whether the columns x .. x+w touch the stretch [a, b)
inline bool spans(int x, int w, int a, int b) { return b > a && x < b && x + w > a; }
}
