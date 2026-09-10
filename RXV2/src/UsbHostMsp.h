// LockDownRadioControl — RXV2  ::  UsbHostMsp.h
//
// MSP over USB for the DONGLE - and, from 0.9.639, for a RECEIVER too
// (Malcolm 2026-09-11: "connect with a USB so that nothing is impossible";
// "Yes let's do it! Selecting simulator mode disables it of course. Otherwise,
// it's like the dongle"). Every Rotorflight flight controller speaks
// MSP on its USB-C socket out of the box - that is how the configurator gets
// in - so a dongle plugged into that socket needs no Ports tab and no wiring.
//
// The ESP32-S3 is the USB HOST here (IDF usb_host library + Espressif's
// CDC-ACM class driver, vendored in lib/usb_host_cdc_acm). Nothing is
// configured by the user: in dongle mode the host stack starts at boot; if a
// serial device enumerates it becomes the flight-controller link, otherwise
// the UART on D5/D6 carries on as before. Bytes arrive in the driver's task
// and are queued; the main loop drains them into mspSerialFeed(), so every
// MSP reply is handled exactly as it is for the UART.
//
// While the host stack owns the socket the board cannot be flashed through
// it by the usual means - WiFi/Bluetooth updates are unaffected, and the
// button-held ROM bootloader still works for a USB flash (the usbmodem port
// is gone while the host runs).
//
// Invariants (0.9.639/0.9.640, a RECEIVER runs this in flight):
//  - the main loop never waits on USB: sends are queued for the usbtx task,
//    bytes in arrive through the driver's task and a stream buffer;
//  - a receiver opens or closes the device only with no transmitter linked
//    for 3 s (mayTouchDevice); an unplug clears `opened` at once so MSP goes
//    back to the CRSF tunnel, and the close itself waits for the link to end;
//  - never queue after `opened` is false; the queue is emptied at every open;
//  - never close a device that is still enumerated (close only on `gone`).
#pragma once
#include <Arduino.h>
#include "1Defs.h"     // dongleEnabled, usbFcEnabled, rx.lastMillis, events

#if defined(CONFIG_IDF_TARGET_ESP32S3) && (ARDUINO_USB_MODE == 0)
#include "usb/usb_host.h"
#include "usb/cdc_acm_host.h"
#include "freertos/stream_buffer.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
// The receiver keeps flying while the command line waits (cliWait): global-scope
// declarations, defined in Radio.h / Output.h / Telemetry.h.
void radioPoll(); void sbusTick(); void protocolRx();

// Where were we when it crashed? RTC memory survives a panic-reboot; the
// boot log reads these back (Dongle 4 panicked on the first 588-byte reply
// over USB, 2026-09-11, and nothing said where).
RTC_NOINIT_ATTR uint32_t usbCrumbPhase;     // 1 dataCb 2 pollDrain 3 feed 4 open 5 send 6 newDev
RTC_NOINIT_ATTR uint32_t usbCrumbLen;
RTC_NOINIT_ATTR uint32_t usbCrumbMagic;     // 0x55B0C0DE when the crumbs are meaningful
namespace UsbHostMsp {
    inline void crumb(uint32_t phase, uint32_t len = 0) { usbCrumbPhase = phase; usbCrumbLen = len; usbCrumbMagic = 0x55B0C0DE; }
    inline void crumbDone() { usbCrumbPhase = 0; }
    inline bool     started   = false;   // host stack up
    inline volatile bool present = false;   // a device has enumerated (new_dev_cb)
    inline volatile bool gone    = false;   // the open device disconnected (event_cb)
    inline bool     opened    = false;   // CDC link open: MSP goes over USB
    inline uint16_t vid = 0, pid = 0;
    inline cdc_acm_dev_hdl_t hdl = nullptr;
    inline StreamBufferHandle_t rxbuf = nullptr;
    inline uint32_t bytesIn = 0, bytesOut = 0, opens = 0, openFails = 0;
    inline uint32_t lastOpenTryMs = 0;
    inline bool     wasOpen   = false;   // an "unplugged" note only after a link existed
    inline volatile uint32_t devSeen = 0;  // bumped by every enumeration; a device that arrived while a close was deferred is not forgotten
    inline uint32_t openedSeen = 0;
    // Sends never block the main loop (0.9.639 - a receiver's 10 ms rule): a frame goes
    // into a queue and a small task does the blocking USB write. hdl is shared with
    // that task under a mutex, so a close can never race a write.
    struct TxItem { uint16_t n; uint8_t d[320]; };
    inline QueueHandle_t     txq = nullptr;
    inline SemaphoreHandle_t hdlMutex = nullptr;
    inline void txTask(void*) {
        static TxItem it;
        for (;;) {
            if (xQueueReceive(txq, &it, portMAX_DELAY) != pdTRUE) continue;
            if (xSemaphoreTake(hdlMutex, pdMS_TO_TICKS(500)) != pdTRUE) continue;
            if (opened && hdl) {
                crumb(5, it.n);
                if (cdc_acm_host_data_tx_blocking(hdl, it.d, it.n, 200) == ESP_OK) bytesOut += it.n;
                crumbDone();
            }
            xSemaphoreGive(hdlMutex);
        }
    }
    inline const char* who() { return dongleEnabled ? "Dongle" : "Receiver"; }
    // A receiver opens or closes the USB device only with no transmitter linked: both
    // calls can block for tens of ms (descriptor fetches, transfer cancels) and the
    // radio loop must never wait on them while the model may fly. A link that is
    // already open stays open - its traffic runs in the driver's task and the queue.
    inline bool mayTouchDevice() { return dongleEnabled || !(rx.lastMillis && (uint32_t)(millis() - rx.lastMillis) < 3000); }   // 3 s: a 1 s gap is an in-flight dropout, not a landing (0.9.640)
    // Rotorflight's command line (0.9.617): '#' on the MSP port enters it,
    // 'save' or 'exit' leave it - both restart the flight controller. While
    // it is open MSP is dead, so the status poll and probes stand down and
    // the bytes go to cliBuf instead of the MSP parser.
    inline volatile bool cliMode = false;
    inline String   cliBuf;
    inline uint32_t cliLines = 0;

    inline void dataCb(uint8_t* data, size_t len, void*) {         // CDC driver task
        crumb(1, len);
        if (rxbuf && len) xStreamBufferSend(rxbuf, data, len, 0);
        crumbDone();
    }
    inline void devCb(const cdc_acm_host_dev_event_data_t* e, void*) {
        if (e && e->type == CDC_ACM_HOST_DEVICE_DISCONNECTED) gone = true;
    }
    inline void newDevCb(usb_device_handle_t dev) {                 // host library task
        crumb(6);
        const usb_device_desc_t* d = nullptr;
        if (usb_host_get_device_descriptor(dev, &d) == ESP_OK && d) { vid = d->idVendor; pid = d->idProduct; }
        devSeen++;
        present = true;
    }
    inline void hostTask(void*) {
        for (;;) {
            uint32_t flags = 0;
            usb_host_lib_handle_events(portMAX_DELAY, &flags);
            if (flags & USB_HOST_LIB_EVENT_FLAGS_NO_CLIENTS) usb_host_device_free_all();
        }
    }
    inline bool begin() {
        if (started) return true;
        rxbuf = xStreamBufferCreate(4096, 1);
        txq = xQueueCreate(6, sizeof(TxItem));
        hdlMutex = xSemaphoreCreateMutex();
        usb_host_config_t hc = {};
        hc.skip_phy_setup = false;
        hc.intr_flags = ESP_INTR_FLAG_LEVEL1;
        if (usb_host_install(&hc) != ESP_OK) { events.add("USB host: install failed"); return false; }
        cdc_acm_host_driver_config_t dc = {};
        dc.driver_task_stack_size = 4096;
        dc.driver_task_priority   = 10;
        dc.xCoreID                = 0;
        dc.new_dev_cb             = newDevCb;
        if (cdc_acm_host_install(&dc) != ESP_OK) { events.add("USB host: CDC driver failed"); return false; }
        xTaskCreatePinnedToCore(hostTask, "usbhost", 4096, nullptr, 9, nullptr, 0);
        xTaskCreatePinnedToCore(txTask,   "usbtx",   4096, nullptr, 5, nullptr, 0);
        started = true;
        events.add("USB host up: a flight controller on the USB socket will be used automatically");
        return true;
    }
    inline bool active() { return opened; }
    inline bool send(const uint8_t* d, size_t n) {
        if (!opened || !hdl || !txq || n == 0 || n > sizeof(TxItem::d)) return false;
        static TxItem it;                                    // main-loop task only (pages, BLE and the CLI all run there)
        it.n = (uint16_t)n; memcpy(it.d, d, n);
        return xQueueSend(txq, &it, 0) == pdTRUE;           // never waits: a full queue is a stuck link, and the caller times out as before
    }
    // Main loop: adopt a new device, drop a gone one, drain received bytes.
    inline void poll() {
        if (!started) return;
        if (gone) {
            opened = false;                                  // at once: MSP falls back to the UART (dongle) or the radio-link tunnel (receiver)
            if (mayTouchDevice() && xSemaphoreTake(hdlMutex, 0) == pdTRUE) {
                gone = false;
                if (hdl) { cdc_acm_host_close(hdl); hdl = nullptr; }
                xSemaphoreGive(hdlMutex);
                if (wasOpen) { char m[96]; snprintf(m, sizeof m, "%s: the USB flight controller was unplugged - back to the %s", who(), dongleEnabled ? "UART" : "radio link"); events.add(m); }
                wasOpen = false;
                if (devSeen == openedSeen) present = false;   // nothing new enumerated since the device we had: wait for the next plug-in
            }
        }
        if (present && !opened && !gone && mayTouchDevice() && (uint32_t)(millis() - lastOpenTryMs) > 500 && xSemaphoreTake(hdlMutex, 0) == pdTRUE) {
            lastOpenTryMs = millis();
            cdc_acm_host_device_config_t cfg = {};
            cfg.connection_timeout_ms = 1000;
            cfg.out_buffer_size = 512;
            cfg.event_cb = devCb;
            cfg.data_cb  = dataCb;
            cfg.user_arg = nullptr;
            crumb(4);
            const bool ok = cdc_acm_host_open(vid, pid, 0, &cfg, &hdl) == ESP_OK;
            if (ok) {
                cdc_acm_line_coding_t lc = { 115200, 0, 0, 8 };
                cdc_acm_host_line_coding_set(hdl, &lc);
                cdc_acm_host_set_control_line_state(hdl, true, true);
                if (txq) xQueueReset(txq);                   // frames meant for the previous device (an FC that restarted) are not fired at this one (0.9.640)
                opened = true; wasOpen = true; opens++; openedSeen = devSeen;
            }
            xSemaphoreGive(hdlMutex);
            if (ok) {
                char m[96]; snprintf(m, sizeof m, "%s: flight controller on USB (%04X:%04X) - MSP over USB, no port setting needed", who(), vid, pid);
                events.add(m);
            } else {
                openFails++;
                if (openFails == 1 || openFails % 20 == 0) { char m[96]; snprintf(m, sizeof m, "USB host: device %04X:%04X is not a serial port (try %lu)", vid, pid, (unsigned long)openFails); events.add(m); }
                if (openFails >= 40) present = false;      // give up on this device until it re-enumerates
            }
        }
        if (rxbuf) {
            uint8_t b[128]; size_t n;
            while ((n = xStreamBufferReceive(rxbuf, b, sizeof b, 0)) > 0) {
                bytesIn += n;
                crumb(2, n);
                if (cliMode) { if (cliBuf.length() < 12000) cliBuf.concat((const char*)b, n); }
                else { crumb(3, n); for (size_t i = 0; i < n; i++) mspSerialFeed(b[i]); }
                crumbDone();
            }
        }
    }
    // --- command line -------------------------------------------------
    inline bool cliPromptSeen() {
        const int L = cliBuf.length();
        return L >= 2 && cliBuf.charAt(L - 1) == ' ' && cliBuf.charAt(L - 2) == '#';
    }
    inline bool cliWait(uint32_t timeoutMs) {          // pump the link until the prompt is back
        // A receiver keeps flying while it waits, exactly as mspRequestAndWait does
        // (0.9.639): the radio, the channel output and the CRSF line are all served.
        const uint32_t t0 = millis();
        while ((uint32_t)(millis() - t0) < timeoutMs) {
            if (!dongleEnabled) { ::radioPoll(); ::sbusTick(); ::protocolRx(); }
            poll();
            if (cliPromptSeen()) return true;
            delay(1);
        }
        return cliPromptSeen();
    }
    inline bool cliEnter(uint32_t timeoutMs) {
        if (!opened) return false;
        if (cliMode) return true;
        cliMode = true; cliBuf = "";
        const uint8_t hash = '#';
        if (!send(&hash, 1)) { cliMode = false; return false; }
        if (!cliWait(timeoutMs)) { cliMode = false; return false; }
        { char m[96]; snprintf(m, sizeof m, "%s: Rotorflight command line open over USB (MSP paused until save/exit)", who()); events.add(m); }
        return true;
    }
    // Send one command, return everything the FC printed up to its next prompt.
    inline bool cliExchange(const String& cmd, String& out, uint32_t timeoutMs) {
        if (!cliMode) return false;
        cliBuf = "";
        String line = cmd; line += "\n";
        if (!send((const uint8_t*)line.c_str(), line.length())) return false;
        const bool ok = cliWait(timeoutMs);
        out = cliBuf;
        // drop the echoed command line and the trailing prompt
        int nl = out.indexOf('\n'); if (nl >= 0 && out.startsWith(cmd)) out = out.substring(nl + 1);
        if (out.endsWith("# ")) out = out.substring(0, out.length() - 2);
        out.trim();
        cliLines++;
        return ok;
    }
    inline void cliLeave(bool save) {
        if (!cliMode) return;
        const char* c = save ? "save\n" : "exit\n";
        send((const uint8_t*)c, strlen(c));
        cliMode = false; cliBuf = "";
        { char m[110]; snprintf(m, sizeof m, save ? "%s: command line 'save' - flight controller restarting" : "%s: command line 'exit' - flight controller restarting, nothing saved", who()); events.add(m); }
    }
    inline void stateJson(String& j) {
        char b[200];
        snprintf(b, sizeof b, ",\"dongle_link\":\"%s\",\"usb_fc\":%s,\"usb\":{\"host\":%s,\"device\":%s,\"vid\":\"%04X\",\"pid\":\"%04X\",\"in\":%lu,\"out\":%lu,\"opens\":%lu,\"fails\":%lu,\"cli\":%s}",
                 opened ? "usb" : "uart", usbFcEnabled ? "true" : "false", started ? "true" : "false", opened ? "true" : "false", vid, pid,
                 (unsigned long)bytesIn, (unsigned long)bytesOut, (unsigned long)opens, (unsigned long)openFails, cliMode ? "true" : "false");
        j += b;
    }
}
#else
namespace UsbHostMsp {
    inline volatile bool cliMode = false;
    inline bool begin() { return false; }
    inline bool active() { return false; }
    inline bool cliEnter(uint32_t) { return false; }
    inline bool cliExchange(const String&, String&, uint32_t) { return false; }
    inline void cliLeave(bool) {}
    inline bool send(const uint8_t*, size_t) { return false; }
    inline void poll() {}
    inline void stateJson(String& j) { j += ",\"dongle_link\":\"uart\",\"usb_fc\":false,\"usb\":{\"host\":false,\"device\":false,\"cli\":false}"; }
}
#endif
