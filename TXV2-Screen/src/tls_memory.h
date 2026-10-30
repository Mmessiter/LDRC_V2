// (1.11.146) THE SECURE CONNECTION'S MEMORY COMES FROM THE PSRAM.
//
// The framework is built with CONFIG_MBEDTLS_INTERNAL_MEM_ALLOC: every byte mbedTLS wants - its two 16 kB record
// buffers, the certificate chain of messiter.com as it is parsed, the handshake's big numbers - is taken from the
// chip's INTERNAL RAM, some 70 kB in all. The 16 MB twin has nowhere near that to spare once the panel's strips, the
// serial buffer and the WiFi have theirs: Mehul's transmitter, 30 Oct 2026, showed the quiet look at power-up failing
// twenty times over with "the certificate of messiter.com was not accepted" (mbedTLS says "verify failed" when it
// could not even parse the chain for want of memory), the internal RAM's low-water mark at 120 bytes, and Malcolm's
// own screen left the WiFi twice that day under the same thrash.
//
// mbedTLS was built with MBEDTLS_PLATFORM_MEMORY: its calloc and free are function pointers, and this file points
// them at the PSRAM (8 MB, 2 MB and more free) before anything has used them - the first thing setup() does. Should
// the PSRAM ever refuse, the internal RAM answers as before (counted). The WiFi's own WPA handshake (built on the
// same mbedTLS) comes along: a task's allocations, which the PSRAM serves as it already serves the WiFi's buffers
// (CONFIG_SPIRAM_TRY_ALLOCATE_WIFI_LWIP). The hardware AES and SHA of the S3 take PSRAM buffers (the framework offers
// CONFIG_MBEDTLS_EXTERNAL_MEM_ALLOC for exactly this).
//
// /status "tls": whether the PSRAM serves, the bytes held now and at most, the allocations made, those the PSRAM refused.
#pragma once
#include <atomic>
#include <esp_heap_caps.h>
#include <mbedtls/platform.h>

static std::atomic<uint32_t> tlsNow{0}, tlsPeak{0}, tlsN{0}, tlsFallback{0};
static bool tlsPsram = false;

static void *tlsCalloc(size_t n, size_t size) {
    void *p = heap_caps_calloc(n, size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!p) { p = heap_caps_calloc(n, size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT); if (p) tlsFallback++; }
    if (p) {
        const uint32_t got = (uint32_t) heap_caps_get_allocated_size(p);
        const uint32_t now = tlsNow.fetch_add(got) + got;
        uint32_t peak = tlsPeak.load(); while (now > peak && !tlsPeak.compare_exchange_weak(peak, now)) {}
        tlsN++;
    }
    return p;
}
static void tlsFree(void *p) {
    if (!p) return;
    tlsNow.fetch_sub((uint32_t) heap_caps_get_allocated_size(p));
    heap_caps_free(p);
}
// Before the WiFi, before anything secure: the pointers are swapped once.
static void tlsMemoryBegin() {
    if (heap_caps_get_free_size(MALLOC_CAP_SPIRAM) < 512 * 1024) return;      // no PSRAM worth the name: as the framework had it
    mbedtls_platform_set_calloc_free(tlsCalloc, tlsFree);
    tlsPsram = true;
}
// The largest piece the secure connection could get now (the pool it draws from): the updater's words and its
// "short of memory" verdict go by this, not by the internal RAM.
static uint32_t tlsRoom() {
    return (uint32_t) heap_caps_get_largest_free_block(tlsPsram ? (MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT) : (MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
}
static std::string tlsJson() {
    char b[140];
    snprintf(b, sizeof b, "\"tls\":{\"psram\":%d,\"now\":%lu,\"peak\":%lu,\"n\":%lu,\"fallback\":%lu,\"room\":%lu}",
             tlsPsram ? 1 : 0, (unsigned long) tlsNow.load(), (unsigned long) tlsPeak.load(), (unsigned long) tlsN.load(), (unsigned long) tlsFallback.load(), (unsigned long) tlsRoom());
    return b;
}
