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
//  - opens and closes run on the usbtx task (0.9.641), so they may happen at
//    any time, transmitter on or off; an unplug clears `opened` at once so
//    MSP goes back to the CRSF tunnel while the task does the close;
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
    inline volatile bool opened = false; // CDC link open: MSP goes over USB (set by the usbtx task, read everywhere)
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
    // Opening and closing the device are the two calls that can wait on the
    // driver (descriptor fetches, transfer cancels: up to seconds if the
    // device misbehaves). From 0.9.641 they run on the usbtx task as well -
    // the main loop only asks (wantOpen/wantClose) and reads the answer
    // (openResult/closeDone), so it never waits on USB at all.
    inline void dataCb(uint8_t* data, size_t len, void*);                       // defined below
    inline void devCb(const cdc_acm_host_dev_event_data_t* e, void*);
    inline volatile bool wantOpen = false, wantClose = false, closeDone = false;
    inline volatile int  openResult = 0;                 // 0 pending/none, 1 opened, -1 failed, -2 device gone
    inline void txTask(void*) {
        static TxItem it;
        for (;;) {
            if (xQueueReceive(txq, &it, pdMS_TO_TICKS(20)) == pdTRUE) {
                if (xSemaphoreTake(hdlMutex, pdMS_TO_TICKS(500)) == pdTRUE) {
                    if (opened && hdl) {
                        crumb(5, it.n);
                        if (cdc_acm_host_data_tx_blocking(hdl, it.d, it.n, 200) == ESP_OK) bytesOut += it.n;
                        crumbDone();
                    }
                    xSemaphoreGive(hdlMutex);
                }
            }
            if (wantClose) {
                if (xSemaphoreTake(hdlMutex, pdMS_TO_TICKS(500)) == pdTRUE) {
                    opened = false;
                    if (hdl) { cdc_acm_host_close(hdl); hdl = nullptr; }
                    xSemaphoreGive(hdlMutex);
                    wantClose = false; closeDone = true;
                }
            }
            if (wantOpen) {
                if (xSemaphoreTake(hdlMutex, pdMS_TO_TICKS(500)) == pdTRUE) {
                    cdc_acm_host_device_config_t cfg = {};
                    cfg.connection_timeout_ms = 1000;
                    cfg.out_buffer_size = 512;
                    cfg.event_cb = devCb;
                    cfg.data_cb  = dataCb;
                    cfg.user_arg = nullptr;
                    crumb(4);
                    const esp_err_t r = cdc_acm_host_open(vid, pid, 0, &cfg, &hdl);
                    if (r == ESP_OK) {
                        cdc_acm_line_coding_t lc = { 115200, 0, 0, 8 };
                        cdc_acm_host_line_coding_set(hdl, &lc);
                        cdc_acm_host_set_control_line_state(hdl, true, true);
                        if (txq) xQueueReset(txq);            // frames meant for the previous device (an FC that restarted) are not fired at this one (0.9.640)
                        opened = true;
                    } else hdl = nullptr;
                    crumbDone();
                    xSemaphoreGive(hdlMutex);
                    openResult = (r == ESP_OK) ? 1 : (r == ESP_ERR_NOT_FOUND ? -2 : -1);
                    wantOpen = false;
                }
            }
        }
    }
    inline const char* who() { return dongleEnabled ? "Dongle" : "Receiver"; }
    // Opening and closing the device can wait for tens of ms (descriptor fetches,
    // transfer cancels) - so from 0.9.641 they run on the usbtx task, and from
    // 0.9.643 they may happen at any time: nothing on the radio loop waits on them,
    // so a flight controller plugged in with the transmitter already on is adopted
    // at once (the bench habit: transmitter on, blades off). The main loop only
    // asks and reads the answer.
    inline bool mayTouchDevice() { return true; }
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
        rxbuf = xStreamBufferCreate(12288, 1);   // one 4 kB dataflash reply is ~4110 bytes on the wire: never let a frame be dropped between poll() passes (0.9.663)
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
        if (cdc_acm_host_install(&dc) != ESP_OK) { events.add("USB host: CDC driver failed"); usb_host_uninstall(); return false; }   // never leave a half-installed host (0.9.642)
        xTaskCreatePinnedToCore(hostTask, "usbhost", 4096, nullptr, 9, nullptr, 0);
        xTaskCreatePinnedToCore(txTask,   "usbtx",   4096, nullptr, 5, nullptr, 0);
        started = true;
        if (dongleEnabled) events.add("USB host up: a flight controller on the USB socket will be used automatically");   // a receiver's boot says it once, in main.cpp
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
        static uint32_t seenAtReset = 0;
        if (devSeen != seenAtReset) { seenAtReset = devSeen; openFails = 0; }   // a fresh enumeration gets fresh tries (0.9.641)
        if (gone && !wantClose && !closeDone) {
            opened = false;                                  // at once: MSP falls back to the UART (dongle) or the radio-link tunnel (receiver)
            if (mayTouchDevice()) wantClose = true;          // the usbtx task closes it; a receiver only once the transmitter is quiet
        }
        if (closeDone) {
            closeDone = false; gone = false;
            ::mspSerialResetParser();                          // half a frame from a device that has gone must not wait for its tail
            if (cliMode) { cliMode = false; cliBuf = ""; events.add("Command line: the flight controller went away - closed, MSP resumes"); }   // never latched by an unplug (0.9.641)
            if (wasOpen) { char m[96]; snprintf(m, sizeof m, "%s: the USB flight controller was unplugged - back to the %s", who(), dongleEnabled ? "UART" : "radio link"); events.add(m); }
            wasOpen = false;
            if (devSeen == openedSeen) present = false;      // nothing new enumerated since the device we had: wait for the next plug-in
        }
        if (openResult != 0) {
            const int r = openResult; openResult = 0;
            if (r == 1) {
                ::mspSerialResetParser();                      // a new device starts a clean frame (the parser now accepts 4200-byte replies: never inherit half a frame)
                wasOpen = true; opens++; openedSeen = devSeen;
                char m[96]; snprintf(m, sizeof m, "%s: flight controller on USB (%04X:%04X) - MSP over USB, no port setting needed", who(), vid, pid);
                events.add(m);
            } else {
                openFails++;
                if (r == -2) present = false;                // the device left before we opened it: nothing to retry
                else if (openFails == 1 || openFails % 20 == 0) { char m[96]; snprintf(m, sizeof m, "USB host: device %04X:%04X is not a serial port (try %lu)", vid, pid, (unsigned long)openFails); events.add(m); }
                if (openFails >= 40) present = false;        // give up on this device until it re-enumerates
            }
        }
        if (present && !opened && !gone && !wantOpen && !wantClose && mayTouchDevice() && (uint32_t)(millis() - lastOpenTryMs) > 500) {
            lastOpenTryMs = millis();
            wantOpen = true;                                 // the usbtx task opens it and reports back
        }
        if (rxbuf) {
            uint8_t b[128]; size_t n;
            while ((n = xStreamBufferReceive(rxbuf, b, sizeof b, 0)) > 0) {
                bytesIn += n;
                crumb(2, n);
                if (cliMode) { cliBuf.concat((const char*)b, n); if (cliBuf.length() > 16000) cliBuf.remove(0, cliBuf.length() - 16000); }   // keep the TAIL: the prompt ends it, however long a dump is (0.9.642)
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
