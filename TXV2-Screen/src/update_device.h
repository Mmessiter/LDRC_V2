// "Check for update" on the screen itself (lib/LdrcUpdate does the thinking; this is the machine it runs on):
// the panel and its two buttons, the downloads from messiter.com (a task on the other core, so the display
// never waits for the WiFi), the screen's own firmware and its trial, and the card.
//
// Included by main.cpp just before setup(). Nothing here runs unless the pilot presses "Check for update",
// except resume() at start-up: a verdict nobody has seen, or firmware on trial.
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Update.h>
#include <esp_ota_ops.h>
#include "LdrcUpdate.h"
#include "ca_bundle.h"

static const char LATEST_URL[] = "https://messiter.com/txv1b/release/latest.txt";
static const char RX_MANIFEST_URL[] = "https://messiter.com/rxv2/release/manifest.json";   // the receivers' releases (RXV2 dev/release.sh publishes it)
static const char SCREEN_MARK[] = "LDRCSCREEN=" SCREEN_VERSION ";";      // the release tool looks for this in the binary

// The core accepts new firmware the moment it starts, unless this says otherwise. We say otherwise: new
// firmware has to show that it can join the WiFi again (and talk to the Teensy) before it is kept;
// until then any restart brings the previous firmware back (ldrc::Updater::trialPoll).
extern "C" bool verifyRollbackLater() { return true; }

// ------------------------------------------------------------------ slow work, on the other core
struct UpdJob { int kind = 0; std::string url, local; uint32_t size = 0, crc = 0; size_t maxBytes = 0; };   // 1 text, 2 file, 3 check, 4 flash
static UpdJob updJob; static ldrc::Work updWork;
static volatile bool updBusy = false, updStop = false; static volatile uint32_t updProgress = 0;
static TaskHandle_t updTaskHandle = nullptr;
static WiFiClientSecure *updTls = nullptr; static HTTPClient *updHttp = nullptr;
static uint8_t *updBuf = nullptr; static const size_t UPD_BUF = 16384;
static volatile uint32_t updFreeKb = 0; static volatile bool updFreeKnown = false;      // the card's free space: asking takes seconds the first time, so the task asks

static void updHangUp() { if (updHttp) updHttp->end(); if (updTls) updTls->stop(); }
static volatile bool updNoMemory = false;                   // (1.11.32) the last ask failed for want of memory: mbedTLS could not get its buffers (-0x7F00), or there is plainly no room
// Ask for `url`; on success the answer's body is waiting and `len` is its length.
static bool updAsk(const std::string &url, int &len, std::string &err) {
    updNoMemory = false;
    if (WiFi.status() != WL_CONNECTED) { err = "the WiFi is not connected"; return false; }
    if (!updTls) { updTls = new WiFiClientSecure(); updTls->setCACert(LDRC_CA_BUNDLE); updTls->setHandshakeTimeout(20); }
    if (!updHttp) { updHttp = new HTTPClient(); updHttp->setReuse(true); updHttp->setUserAgent("LDRC-V1B-screen/" SCREEN_VERSION); }
    updHttp->setConnectTimeout(12000); updHttp->setTimeout(15000);
    if (!updHttp->begin(*updTls, url.c_str())) { err = "the address is not understood"; return false; }
    const int code = updHttp->GET();
    if (code != 200) {
        char why[96] = ""; const int tls = updTls->lastError(why, sizeof why);
        if (code > 0) { char b[48]; snprintf(b, sizeof b, "messiter.com answered %d", code); err = b; }
        else if (tls == -0x2700) err = "the certificate of messiter.com was not accepted";      // MBEDTLS_ERR_X509_CERT_VERIFY_FAILED
        else {
            err = "no connection to messiter.com"; if (tls) { char b[64]; snprintf(b, sizeof b, " (%d, -0x%04X)", code, (unsigned) -tls); err += b; } else { char b[24]; snprintf(b, sizeof b, " (%d)", code); err += b; }
            updNoMemory = tls == -0x7F00 || ESP.getMaxAllocHeap() < 40000;   // MBEDTLS_ERR_SSL_ALLOC_FAILED: the updater restarts the screen once for this (1.11.32)
            // 1.11.11 (Malcolm, 7 Oct: "could not join the Wi-Fi usefully until I had switched the transmitter off and on",
            // twice): a TLS connection wants some 45 kB of memory in one piece; after a Bluetooth session there may not be.
            // The numbers go into the message, so the next time says which it was.
            { char b[64]; snprintf(b, sizeof b, " [heap %u, largest %u, rssi %d]", (unsigned) ESP.getFreeHeap(), (unsigned) ESP.getMaxAllocHeap(), (int) WiFi.RSSI()); err += b; }
        }
        updHangUp();
        return false;
    }
    len = updHttp->getSize();
    if (len < 0) { err = "messiter.com did not say how long the file is"; updHangUp(); return false; }
    return true;
}
// Read the body, handing each piece to `sink` (false from it = stop). Leaves the connection open for the next file.
template <class Sink> static bool updRead(int len, std::string &err, Sink sink) {
    WiFiClient *s = updHttp->getStreamPtr();
    if (!s) { err = "the connection was lost"; updHangUp(); return false; }      // (it went between the headers and the first byte)
    uint32_t got = 0, idle = millis();
    while (got < (uint32_t) len) {
        if (updStop) { err = "cancelled"; break; }
        int n = s->available();
        if (n > 0) {
            n = s->read(updBuf, min((size_t) n, min(UPD_BUF, (size_t) ((uint32_t) len - got))));
            if (n > 0) { if (!sink(updBuf, (size_t) n)) { if (err.empty()) err = "the screen's card would not take it"; break; } got += n; idle = millis(); updProgress = got; continue; }
        }
        if (!s->connected() && s->available() <= 0) { err = "the connection was lost"; break; }
        if (millis() - idle > 15000) { err = "messiter.com stopped answering"; break; }
        vTaskDelay(pdMS_TO_TICKS(2));
    }
    if (got == (uint32_t) len && err.empty()) { updHttp->end(); return true; }       // (kept alive for the next one)
    updHangUp();
    return false;
}
// `from` takes the place of `to` on the screen's card. FAT cannot rename over a file, so the file that is there
// is moved aside first, and removed last; what is being done is written down (one line, /update/placing.txt),
// so that a power cut between the two renames is put right at the next start (updMend).
static const char UPD_PLACING[] = "/update/placing.txt";
static bool updReplace(const std::string &from, const std::string &to, bool note) {
    if (!SD.exists(from.c_str())) return false;
    sdMakeFolders(to.c_str());
    const std::string aside = to + ".old";
    const bool was = SD.exists(to.c_str());
    if (was) {
        if (note) { File j = SD.open(UPD_PLACING, FILE_WRITE); if (j) { j.print(to.c_str()); j.close(); } }
        SD.remove(aside.c_str());
        if (!SD.rename(to.c_str(), aside.c_str())) { if (note) SD.remove(UPD_PLACING); return false; }
    }
    if (!SD.rename(from.c_str(), to.c_str())) { if (was) SD.rename(aside.c_str(), to.c_str()); if (was && note) SD.remove(UPD_PLACING); return false; }
    if (was) { SD.remove(aside.c_str()); if (note) SD.remove(UPD_PLACING); }
    return true;
}
static void updMend() {                                     // at start-up, before a page is read from the card
    if (!sdOk || !SD.exists(UPD_PLACING)) return;
    File j = SD.open(UPD_PLACING, FILE_READ); std::string to;
    if (j) { while (j.available() && to.size() < 200) to.push_back((char) j.read()); j.close(); }
    if (to.size() > 1 && to[0] == '/') {
        const std::string aside = to + ".old";
        if (!SD.exists(to.c_str()) && SD.exists(aside.c_str())) { SD.rename(aside.c_str(), to.c_str()); blog("boot", "put back after a power cut: " + to); }
        else if (SD.exists(aside.c_str())) SD.remove(aside.c_str());
    }
    SD.remove(UPD_PLACING);
}
// What the CARD holds, read back: its size and its checksum.
static bool updReadBack(const std::string &path, uint32_t &size, uint32_t &crc) {
    File f = SD.open(path.c_str(), FILE_READ);
    if (!f || f.isDirectory()) { if (f) f.close(); return false; }
    size = 0; crc = 0; int n, turns = 0;
    while ((n = f.read(updBuf, UPD_BUF)) > 0) { crc = ldrc::crc32(updBuf, (size_t) n, crc); size += (uint32_t) n; if ((++turns & 7) == 0) vTaskDelay(1); if (updStop) break; }
    f.close();
    return n == 0 && !updStop;
}
static void updFetchText(ldrc::Work &w) {
    int len = 0;
    std::string url = updJob.url;
    if (url.size() > 10 && url.compare(url.size() - 10, 10, "latest.txt") == 0) { char b[24]; snprintf(b, sizeof b, "?n=%lu", (unsigned long) esp_random()); url += b; }   // never an old copy from a cache on the way
    if (!updAsk(url, len, w.error)) return;
    if ((size_t) len > updJob.maxBytes) { w.error = "the answer is too long"; updHangUp(); return; }
    std::string text; text.reserve(len);
    uint32_t crc = 0;
    if (!updRead(len, w.error, [&](const uint8_t *b, size_t n) { text.append((const char *) b, n); crc = ldrc::crc32(b, n, crc); return true; })) return;
    w.text = text; w.size = (uint32_t) len; w.crc = crc; w.ok = true;
}
static void updFetchFile(ldrc::Work &w) {
    int len = 0;
    if (!sdOk) { w.error = "the screen's card is not there"; return; }
    if (!updAsk(updJob.url, len, w.error)) return;
    if ((uint32_t) len != updJob.size) { w.error = "its length is not what the list names"; updHangUp(); return; }
    const std::string part = updJob.local + ".part";
    sdMakeFolders(part.c_str()); SD.remove(part.c_str());
    File f = SD.open(part.c_str(), FILE_WRITE);
    if (!f) { w.error = "the screen's card would not take it"; updHangUp(); return; }
    uint32_t crc = 0;
    const bool got = updRead(len, w.error, [&](const uint8_t *b, size_t n) { crc = ldrc::crc32(b, n, crc); return f.write(b, n) == n; });
    f.close();
    if (got && crc != updJob.crc) { w.error = "what arrived is not what the list names"; }
    if (!got || crc != updJob.crc) { SD.remove(part.c_str()); return; }
    // What arrived was right. Is what the CARD holds? (close() does not say when the card is full.)
    uint32_t size = 0, held = 0;
    if (!updReadBack(part, size, held) || size != (uint32_t) len || held != crc) { SD.remove(part.c_str()); w.error = updStop ? "cancelled" : "the screen's card did not keep what was written (is it full?)"; return; }
    if (!updReplace(part, updJob.local, false)) { SD.remove(part.c_str()); w.error = "the screen's card would not take it"; return; }
    w.size = (uint32_t) len; w.crc = crc; w.ok = true;
}
static void updCheckFile(ldrc::Work &w) {
    File f = sdOk ? SD.open(updJob.local.c_str(), FILE_READ) : File();
    if (!f || f.isDirectory()) { if (f) f.close(); w.error = "no such file"; return; }
    uint32_t crc = 0, size = 0; int n;
    int turns = 0;
    while ((n = f.read(updBuf, UPD_BUF)) > 0) { crc = ldrc::crc32(updBuf, (size_t) n, crc); size += n; updProgress = size; if ((++turns & 7) == 0) vTaskDelay(1); if (updStop) break; }
    f.close();
    if (updStop) { w.error = "cancelled"; return; }
    w.size = size; w.crc = crc; w.ok = true;
}
// The screen's own firmware, from the file on the card into the spare half of the flash. The half that is
// running is not touched: until the very end (and the restart) the screen is as it was.
//
// 1.11.5. The core's last step, Update.end(), has the chip check what was written (its header, its segments, its
// SHA-256) and name it as the one to start. On Malcolm's transmitter 1.11.4 failed there ("Could Not Activate The
// Firmware") though every byte given to the flash had the right CRC, and the chip's reason went out on the wire to
// the main board, unread. So now: the written half is read back and compared BEFORE the chip is asked (a flash that
// did not keep what it was given is named as such), the system's own lines logged during the check are put in the
// message (sysSince), and the whole write is tried a second time by itself before anyone is told.
static bool updFlashOnce(std::string &why, uint32_t &size, uint32_t &crcOut) {
    why.clear();
    File f = sdOk ? SD.open(updJob.local.c_str(), FILE_READ) : File();
    if (!f || f.isDirectory() || f.size() != updJob.size) { if (f) f.close(); why = "the firmware file on the card is not the one fetched"; return false; }
    if (!Update.begin(updJob.size, U_FLASH)) { why = std::string("the flash would not start (") + Update.errorString() + ")"; f.close(); return false; }
    const esp_partition_t *part = esp_ota_get_next_update_partition(NULL);   // the half the core writes (it asks the same question in begin())
    uint32_t crc = 0, body = 0, done = 0; int n, turns = 0;
    while ((n = f.read(updBuf, UPD_BUF)) > 0) {
        if (updStop) { why = "cancelled"; break; }        // given up (it took too long, or the pilot is flying): the image is NOT named as the one to start
        crc = ldrc::crc32(updBuf, (size_t) n, crc);
        const uint32_t skip = done < 16 ? min<uint32_t>(16 - done, (uint32_t) n) : 0;     // the CRC of everything after the 16-byte header, which the core holds back until end()
        body = ldrc::crc32(updBuf + skip, (size_t) n - skip, body);
        if (Update.write(updBuf, (size_t) n) != (size_t) n) { why = std::string("the flash would not take it (") + Update.errorString() + ")"; break; }
        done += n; updProgress = done;
        if ((++turns & 3) == 0) vTaskDelay(1);
    }
    f.close();
    if (why.empty() && updStop) why = "cancelled";
    if (why.empty() && (done != updJob.size || crc != updJob.crc)) why = "the firmware file on the card is damaged";
    if (why.empty() && part) {                               // read back: from byte 16 on, the flash holds exactly what it was given
        uint32_t held = 0, at = 16;
        while (at < updJob.size) {
            const size_t n2 = min((size_t) UPD_BUF, (size_t) (updJob.size - at));
            if (esp_partition_read(part, at, updBuf, n2) != ESP_OK) { why = "the flash could not be read back"; break; }
            held = ldrc::crc32(updBuf, n2, held); at += (uint32_t) n2;
            if ((++turns & 3) == 0) vTaskDelay(1);
        }
        if (why.empty() && held != body) why = "the flash did not keep what was written";
    }
    if (!why.empty()) { Update.abort(); return false; }
    const uint32_t mark = sysN;
    if (!Update.end(false)) {                                // the chip checks the image, then names it as the one to start
        const std::string reason = sysSince(mark);
        why = std::string("the new firmware was not accepted by the flash (") + Update.errorString() + (reason.empty() ? "" : ": " + reason) + ")";
        return false;
    }
    size = done; crcOut = crc;
    return true;
}
static void updFlash(ldrc::Work &w) {
    std::string why, first;
    for (int attempt = 1; attempt <= 2; ++attempt) {
        uint32_t size = 0, crc = 0;
        if (updFlashOnce(why, size, crc)) { w.size = size; w.crc = crc; w.ok = true; return; }
        if (updStop || why == "cancelled") break;
        if (attempt == 1) { first = why; vTaskDelay(pdMS_TO_TICKS(500)); }   // once more, from the file on the card again
    }
    w.error = first.empty() || first == why ? why + (first.empty() ? "" : ", twice") : "first " + first + ", then " + why;
}
static void updTask(void *) {
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (!updBusy) continue;
        ldrc::Work w;
        // The card's driver and the flash wait in loops that do not sleep: a long file, or the card counting its
        // free space for the first time, can keep this core's idle task from running for more than the five
        // seconds its watchdog allows - and the screen would restart in the middle of an update.
        disableCore0WDT();
        switch (updJob.kind) {
        case 1: updFetchText(w); break;
        case 2: updFetchFile(w); break;
        case 3: updCheckFile(w); break;
        case 4: updFlash(w); break;
        default: w.error = "no such job"; break;
        }
        if (updStop && !w.ok) w.error = "cancelled";
        if (!w.ok && updNoMemory && !updStop) w.memory = true;
        if (sdOk && (!updFreeKnown || updJob.kind == 2)) {
            const uint64_t total = SD.totalBytes(), used = SD.usedBytes();
            if (total > 0 && used <= total) { updFreeKb = (uint32_t) ((total - used) / 1024); updFreeKnown = true; }      // (a card that answers nothing is asked again)
        }
        enableCore0WDT();
        updWork = w;
        updBusy = false;                                   // last: the result is complete before anyone may read it
    }
}
static void updStart(int kind, const std::string &url, const std::string &local, uint32_t size, uint32_t crc, size_t maxBytes) {
    if (updBusy) return;
    if (!updBuf) updBuf = (uint8_t *) ps_malloc(UPD_BUF);
    if (!updTaskHandle) xTaskCreatePinnedToCore(updTask, "update", 24576, nullptr, 1, &updTaskHandle, 0);
    if (!updBuf || !updTaskHandle) { updWork = ldrc::Work(); updWork.error = "the screen is out of memory"; return; }
    updJob.kind = kind; updJob.url = url; updJob.local = local; updJob.size = size; updJob.crc = crc; updJob.maxBytes = maxBytes;
    updWork = ldrc::Work(); updProgress = 0; updStop = false;
    updBusy = true;
    xTaskNotifyGive(updTaskHandle);
}

// ------------------------------------------------------------------ the machine, as the updater sees it
struct ScreenHost : public ldrc::UpdateHost {
    uint32_t ms() override { return millis(); }
    std::string screenVersion() override { return SCREEN_VERSION; }
    std::string stamp() override { return lastDateTime; }
    bool armed() override { return armedNow; }
    int flying() override { return flyingNow(); }
    bool teensySeen() override { return teensyCommands > 0; }
    void wifiWanted(bool on) override {
        if (updWifi == on) return;
        updWifi = on;
        if (on) bleOffForTheUpdate();                       // (1.11.20) the pipe is let go first: awake WiFi and Bluetooth do not mix (the crash of 7 Oct)
        wifiApplySleep();                                   // awake while we fetch (once Bluetooth is down: blePoll applies it then): a radio that dozes between beacons fetches at a crawl
        applyRadios(on ? "WiFi on for the update" : "WiFi off again");
    }
#ifdef LDRC_TEST_FAIL_TRIAL                               // a build that never finds the WiFi while it is on trial: the fall-back, tried out for real
    bool wifiUp() override { return !onTrial() && radiosLive && WiFi.status() == WL_CONNECTED; }
#else
    bool wifiUp() override { return radiosLive && WiFi.status() == WL_CONNECTED; }
#endif
    bool wifiAny() override { return !wifiKnown.empty(); }
    void wifiSetup() override { wifiRequested = true; }
    void keepAwake() override { flushOut(); Serial.write((const uint8_t *) "UKRULES", 7); }      // what every page sends when its background is touched
    // The receiver, through the main board (B11): its last word, and the order (an ordinary touch-event text, as the knock is).
    bool rxNews(ldrc::RxNews &out) override { if (!rxNewsAny) return false; out = ::rxNews; return true; }
    void rxOrder(int major, int minor, int minimus) override {
        char b[40]; snprintf(b, sizeof b, "%s %d %d %d", LDRC_RX_UPDATE_WORD, major, minor, minimus);
        flushOut(); Serial.write((const uint8_t *) b, strlen(b));
    }

    void fetchText(const std::string &url, size_t maxBytes) override { updStart(1, url, "", 0, 0, maxBytes); }
    void fetchFile(const std::string &url, const std::string &local, uint32_t size, uint32_t crc) override { updStart(2, url, local, size, crc, 0); }
    void checkFile(const std::string &local) override { updStart(3, "", local, 0, 0, 0); }
    void flashScreen(const std::string &local, uint32_t size, uint32_t crc) override { updStart(4, "", local, size, crc, 0); }
    bool busy() override { return updBusy; }
    uint32_t progress() override { return updProgress; }
    const ldrc::Work &done() override { return updWork; }
    void stopWork() override { if (updBusy) updStop = true; }

    bool exists(const std::string &p) override { return sdOk && SD.exists(p.c_str()); }
    int32_t sizeOf(const std::string &p) override {
        File f = sdOk ? SD.open(p.c_str(), FILE_READ) : File();
        if (!f || f.isDirectory()) { if (f) f.close(); return -1; }
        const int32_t n = (int32_t) f.size(); f.close();
        return n;
    }
    bool remove(const std::string &p) override { if (!sdOk) return false; SD.remove((p + ".old").c_str()); SD.remove((p + ".new").c_str()); return SD.remove(p.c_str()); }
    bool rename(const std::string &from, const std::string &to) override { return sdOk && updReplace(from, to, true); }
    bool readText(const std::string &p, std::string &out, size_t maxBytes) override {
        File f = sdOk ? SD.open(p.c_str(), FILE_READ) : File();
        if (!f && sdOk && SD.exists((p + ".old").c_str())) f = SD.open((p + ".old").c_str(), FILE_READ);      // a power cut while it was being written: what it said before
        if (!f || f.isDirectory() || (size_t) f.size() > maxBytes) { if (f) f.close(); return false; }
        out.resize(f.size());
        const bool ok = out.empty() || f.read((uint8_t *) &out[0], out.size()) == out.size();
        f.close();
        return ok;
    }
    bool writeText(const std::string &p, const std::string &t) override {      // the new text is whole on the card before the old one goes
        if (!sdOk) return false;
        const std::string fresh = p + ".new";
        sdMakeFolders(p.c_str()); SD.remove(fresh.c_str());
        File f = SD.open(fresh.c_str(), FILE_WRITE); if (!f) return false;
        const bool ok = f.write((const uint8_t *) t.data(), t.size()) == t.size();
        f.close();
        if (!ok) { SD.remove(fresh.c_str()); return false; }
        return updReplace(fresh, p, false);
    }
    bool appendText(const std::string &p, const std::string &t) override {
        if (!sdOk) return false;
        sdMakeFolders(p.c_str());
        size_t size = 0;
        { File r = SD.open(p.c_str(), FILE_READ); if (r) { size = r.size(); r.close(); } }     // (asked of a file open for APPENDING, size() answered nonsense: every line began a new record)
        if (size > 200000) { const std::string old = p + ".old"; SD.remove(old.c_str()); SD.rename(p.c_str(), old.c_str()); }   // the record does not grow for ever
        File f = SD.open(p.c_str(), FILE_APPEND); if (!f) return false;
        const bool ok = f.write((const uint8_t *) t.data(), t.size()) == t.size();
        f.close();
        return ok;
    }
    uint32_t freeKb() override {
        if (!sdOk) return 0;
        if (updFreeKnown) return updFreeKb;
        const uint64_t total = SD.totalBytes(), used = SD.usedBytes();
        return total > 0 && used <= total ? (uint32_t) ((total - used) / 1024) : 0xFFFFFFFFu;      // a card that cannot say is not a full card: the writing itself will tell
    }

    std::string backupFolder(const std::string &firmwareNow) override { return keepNewFolder(firmwareNow); }
    void backupDone(const std::string &folder, const std::string &about) override { keepDone(folder, about); }
    void tidy(const std::string &folder) override {
        if (!sdOk) return;
        File d = SD.open(folder.c_str());
        if (!d || !d.isDirectory()) { if (d) d.close(); return; }
        std::vector<std::string> gone; File f;
        while ((f = d.openNextFile())) { if (!f.isDirectory() && gone.size() < 400) gone.push_back(folder + "/" + f.name()); f.close(); }
        d.close();
        for (auto &p : gone) SD.remove(p.c_str());
    }

    bool onTrial() override {
        const esp_partition_t *run = esp_ota_get_running_partition(); esp_ota_img_states_t st;
        return run && esp_ota_get_state_partition(run, &st) == ESP_OK && st == ESP_OTA_IMG_PENDING_VERIFY;
    }
    void accept() override { esp_ota_mark_app_valid_cancel_rollback(); }
    bool reject() override { flushOut(); delay(200); esp_ota_mark_app_invalid_rollback_and_reboot(); return false; }   // comes back only if there is nothing to go back to
    void restart() override { flushOut(); delay(200); ESP.restart(); }
    uint32_t roomForTls() override { return (uint32_t) ESP.getMaxAllocHeap(); }   // (1.11.31) the largest piece of internal memory: mbedTLS takes its buffers from nowhere else (CONFIG_MBEDTLS_INTERNAL_MEM_ALLOC)
};
static ScreenHost updHost;
static ldrc::Updater updater(updHost, teensyLink, LATEST_URL);
static struct UpdaterSetup { UpdaterSetup() { updater.setReceiverManifest(RX_MANIFEST_URL); } } updaterSetup;   // (the receiver's own update: screen 1.3.0)

// ------------------------------------------------------------------ the panel
// Solid colours, large type, at most two buttons. It lives on its own layer (topFb): present() lays it
// over the page, so the Teensy can go on drawing underneath.
static const int UPD_X = 40, UPD_Y = 36, UPD_W = 720, UPD_H = 408;
struct UpdButton { int x = 0, y = 0, w = 0, h = 0; bool there = false; };
static UpdButton updBtn[3];
static int updBtnFont = 0;                                // the one font of the panel's buttons (updDrawPanel chooses it)
static UpdButton updRow[4];                                 // the versions to choose from: touched, a row is press(10 + its place)
static int updBarX = 0, updBarY = 0, updBarW = 0, updBarH = 0; static bool updBarThere = false; static uint16_t updBack = 0;
static int updPressed = 0;                                 // what is under the finger: a button (1..3) or a row (10..13)
static std::string updPressedName;                         // ... and what it said when the finger came down
static bool updRedraw = false;

static void updText(int x, int y, int font, uint16_t col, const std::string &s) { gfx->startWrite(); drawGlyphs(x, y, font, col, s); gfx->endWrite(); }
static std::string updCut(const std::string &s, int font, int maxW) {                 // what fits, with dots if something had to go
    if (textWidth(font, s) <= maxW) return s;
    std::string t = s;
    while (!t.empty() && textWidth(font, t + "...") > maxW) t.erase(t.size() - 1);
    return t + "...";
}
static void updDrawButton(int i, const std::string &label) {
    UpdButton &b = updBtn[i];
    if (!b.there) return;
    const bool down = updPressed == i + 1;
    const uint16_t face = down ? 0x9CD3 : 0xD69A, hi = shade(face, 60), lo = shade(face, -45);
    gfx->fillRect(b.x, b.y, b.w, b.h, face);
    for (int k = 0; k < 3; ++k) {
        gfx->drawFastHLine(b.x + k, b.y + k, b.w - 2 * k, down ? lo : hi); gfx->drawFastVLine(b.x + k, b.y + k, b.h - 2 * k, down ? lo : hi);
        gfx->drawFastHLine(b.x + k, b.y + b.h - 1 - k, b.w - 2 * k, down ? hi : lo); gfx->drawFastVLine(b.x + b.w - 1 - k, b.y + k, b.h - 2 * k, down ? hi : lo);
    }
    const int font = updBtnFont;   // (one font for every button of the panel: chosen in updDrawPanel)
    updText(b.x + (b.w - textWidth(font, label)) / 2 + (down ? 1 : 0), b.y + (b.h - fontHeight(font)) / 2 + (down ? 1 : 0), font, 0x0000, updCut(label, font, b.w - 12));
}
static void updDrawBar(const ldrc::UpdView &v) {
    if (!updBarThere) return;
    gfx->fillRect(updBarX, updBarY, updBarW, updBarH, updBack);
    gfx->drawRect(updBarX, updBarY, updBarW, updBarH, OUR_INK); gfx->drawRect(updBarX + 1, updBarY + 1, updBarW - 2, updBarH - 2, OUR_INK);
    const uint32_t total = v.barTotal ? v.barTotal : 1, done = min(v.barDone, total);
    const int w = (int) ((uint64_t) (updBarW - 8) * done / total);
    if (w > 0) gfx->fillRect(updBarX + 4, updBarY + 4, w, updBarH - 8, 0x07E0);
}
static void updDrawPanel(const ldrc::UpdView &v) {
    using ldrc::UpdView;
    const bool mine = v.kind != UpdView::GOOD && v.kind != UpdView::BAD;                          // (the pilot's colours, unless it is good or bad news)
    const uint16_t ink = mine ? OUR_INK : 0xFFFF, soft = mine ? OUR_SOFT : 0xC618, warn = 0xFFE0;
    updBack = v.kind == UpdView::GOOD ? 0x0320 : v.kind == UpdView::BAD ? 0x8000 : OUR_PANEL;   // solid: dark green, dark red, the panels' colour
    const uint16_t head = v.kind == UpdView::GOOD ? 0x0220 : v.kind == UpdView::BAD ? 0x5800 : OUR_STRIP;
    const int x = UPD_X, y = UPD_Y, w = UPD_W, h = UPD_H;
    gfx->fillRect(x, y, w, h, updBack);
    gfx->fillRect(x, y, w, 64, head);
    for (int k = 0; k < 3; ++k) gfx->drawRect(x + k, y + k, w - 2 * k, h - 2 * k, ink);
    gfx->drawFastHLine(x, y + 64, w, ink); gfx->drawFastHLine(x, y + 65, w, ink);
    clipX0 = x + 6; clipY0 = y + 4; clipX1 = x + w - 6; clipY1 = y + h - 4;
    { const int font = textWidth(0, v.title) <= w - 40 ? 0 : 6; updText(x + (w - textWidth(font, v.title)) / 2, y + (64 - fontHeight(font)) / 2 + 2, font, ink, v.title); }

    const bool anyButton = !v.button1.empty() || !v.button2.empty();
    // The versions to choose from: a row each, the one installed in green.
    for (int i = 0; i < 4; ++i) updRow[i].there = false;
    int listH = 0;
    for (size_t i = 0; i < v.choices.size() && i < 4; ++i) {
        UpdButton &r = updRow[i]; r.there = true; r.x = x + 30; r.w = w - 60; r.h = 52; r.y = y + 74 + (int) i * 58;
        const bool down = updPressed == 10 + (int) i;
        const uint16_t face = down ? 0x4C9A : v.choices[i].current ? 0x0320 : 0x2A72;
        gfx->fillRect(r.x, r.y, r.w, r.h, face); gfx->drawRect(r.x, r.y, r.w, r.h, shade(face, 40));
        const std::string tag = v.choices[i].current ? "Installed" : v.choices[i].note;
        const int tw = textWidth(2, tag);
        updText(r.x + r.w - 16 - tw, r.y + (r.h - fontHeight(2)) / 2 + 2, 2, v.choices[i].current ? 0x87F0 : soft, tag);
        updText(r.x + 16, r.y + (r.h - fontHeight(6)) / 2 + 2, 6, ink, updCut(v.choices[i].name, 6, r.w - 48 - tw));
        listH = (int) (i + 1) * 58;
    }
    const int top = y + 76 + listH, bottom = anyButton ? y + h - 96 : y + h - 16, room = bottom - top;
    // what there is to show, and how tall it is
    bool three = false; for (auto &r : v.rows) if (!r.next.empty()) three = true;
    const int cWhat = x + (three ? 28 : 110), cNow = x + (three ? 212 : 330), cNext = x + 468;
    const int wWhat = cNow - cWhat - 10, wNow = three ? cNext - cNow - 10 : x + w - 24 - cNow, wNext = x + w - 20 - cNext;
    int rowFont = 6;
    for (auto &r : v.rows) if (textWidth(6, r.what) > wWhat || textWidth(6, r.now) > wNow || (three && textWidth(6, r.next) > wNext)) rowFont = 2;
    const int rowH = fontHeight(rowFont) + 12, headH = three ? 30 : 0;
    const int tableH = v.rows.empty() ? 0 : headH + (int) v.rows.size() * rowH + 8;
    const int fixedH = tableH + (v.warning.empty() ? 0 : 76) + (v.hint.empty() ? 0 : 30) + (v.bar ? 44 : 0);
    static const int tryFonts[3] = { 6, 2, 4 };
    int lineFont = 6; std::vector<std::string> shown;
    for (int f = 0; f < 3; ++f) {
        lineFont = tryFonts[f]; shown.clear();
        for (auto &l : v.lines) { if (l.empty()) continue; for (auto &part : textLines(l, lineFont, w - 64, true)) shown.push_back(part); }
        if ((int) shown.size() * (fontHeight(lineFont) + 6) + fixedH <= room) break;
    }
    const int lineH = fontHeight(lineFont) + 6;
    while (!shown.empty() && (int) shown.size() * lineH + fixedH > room) shown.pop_back();          // (never over the buttons)
    const int all = fixedH + (int) shown.size() * lineH;
    int cy = top + max(0, (room - all) / 2);

    if (!v.rows.empty()) {
        if (three) { updText(cNow, cy, 2, soft, "Now"); updText(cNext, cy, 2, soft, "New"); cy += headH; }
        for (auto &r : v.rows) {
            updText(cWhat, cy + 6, rowFont, soft, updCut(r.what, rowFont, wWhat));
            updText(cNow, cy + 6, rowFont, ink, updCut(r.now, rowFont, wNow));
            if (three) updText(cNext, cy + 6, rowFont, r.next.empty() ? soft : warn, updCut(r.next, rowFont, wNext));
            cy += rowH;
        }
        cy += 8;
    }
    for (auto &l : shown) { updText(x + (w - textWidth(lineFont, l)) / 2, cy + 3, lineFont, ink, l); cy += lineH; }
    updBarThere = v.bar;
    if (v.bar) { updBarX = x + 50; updBarY = cy + 8; updBarW = w - 100; updBarH = 28; updDrawBar(v); cy += 44; }
    if (!v.warning.empty()) {                                // large and bold (struck twice, one pixel apart): it must not be missed
        const int wf = textWidth(1, v.warning) <= w - 40 ? 1 : 0, wx = x + (w - textWidth(wf, v.warning)) / 2;
        updText(wx, cy + 6, wf, warn, v.warning); updText(wx + 1, cy + 6, wf, warn, v.warning);
        cy += wf == 1 ? 76 : 44;
    }
    if (!v.hint.empty()) { updText(x + (w - textWidth(2, v.hint)) / 2, cy, 2, soft, v.hint); cy += 30; }

    // THE BUTTONS (screen 1.4.6; Malcolm, 2-10-2026: "improve the buttons and fonts on this screen"): all the same width,
    // side by side and centred, and all in ONE font - the largest in which every label fits (Arial 32 bold, else 28,
    // else 24). Three buttons came out 250/150/256 wide before, each in its own font, and "Earlier versions" overran.
    updBtn[0].there = !v.button1.empty(); updBtn[1].there = !v.button2.empty(); updBtn[2].there = !v.button3.empty();
    const int by = y + h - 84, bh = 64;
    {
        const std::string *labels[3] = { &v.button1, &v.button2, &v.button3 };
        int n = 0, idx[3];
        for (int i = 0; i < 3; ++i) if (updBtn[i].there) idx[n++] = i;
        const int gap = 20, side = 24;
        const int bw = n ? min(280, (w - 2 * side - (n - 1) * gap) / n) : 0;
        int bx = x + (w - (n * bw + (n - 1) * gap)) / 2;
        for (int k = 0; k < n; ++k) { updBtn[idx[k]].x = bx; updBtn[idx[k]].w = bw; bx += bw + gap; }
        static const int fonts[3] = { 0, 6, 2 };
        updBtnFont = 2;
        for (int f : fonts) {
            bool fits = true;
            for (int k = 0; k < n; ++k) if (textWidth(f, *labels[idx[k]]) > bw - 24) fits = false;
            if (fits) { updBtnFont = f; break; }
        }
    }
    for (int i = 0; i < 3; ++i) { updBtn[i].y = by; updBtn[i].h = bh; }
    updDrawButton(0, v.button1); updDrawButton(1, v.button2); updDrawButton(2, v.button3);
    clipX0 = 0; clipY0 = 0; clipX1 = W; clipY1 = H;
}
static bool updPanelUp() { return topOn && topWho == 1; }
static bool updShowing() { return updater.showing(); }
static bool updChanging() { return updater.working(); }
static bool updHoldsLight() { const ldrc::UpdView::Kind k = updater.view().kind; return k == ldrc::UpdView::BUSY || k == ldrc::UpdView::WORKING; }
static bool updHasLink() { return updater.ownsLink() || updater.showing(); }
static bool updAtWork() { return !updater.idle() || updater.ownsLink() || updBusy; }
static std::string updButtonName(int b) {                  // the panel it is on, and what it says
    const ldrc::UpdView &v = updater.view();
    return v.title + "\n" + (b == 1 ? v.button1 : b == 2 ? v.button2 : b == 3 ? v.button3 : (b >= 10 && (size_t) (b - 10) < v.choices.size()) ? v.choices[b - 10].name : std::string());
}
static int updButtonAt(int px, int py) {
    for (int i = 0; i < 3; ++i) if (updBtn[i].there && px >= updBtn[i].x - 5 && px < updBtn[i].x + updBtn[i].w + 5 && py >= updBtn[i].y - 8 && py < updBtn[i].y + updBtn[i].h + 8) return i + 1;
    for (int i = 0; i < 4; ++i) if (updRow[i].there && px >= updRow[i].x && px < updRow[i].x + updRow[i].w && py >= updRow[i].y - 3 && py < updRow[i].y + updRow[i].h + 3) return 10 + i;
    return 0;
}
// The panel has the screen: a touch is for its buttons and for nothing else. One exception: when the
// Teensy has blanked the screen, the touch wakes it (the blank page's own event), as it always did.
static void updTouch(bool pressed, int x, int y, uint32_t now) {
    { static uint32_t lastDownHere = 0; if (pressed) lastDownHere = now;   // a corner held (the door, the radios): that finger is not for this page (1.11.3)
      if (touchLockout) { if (!pressed && (int32_t) (now - lastDownHere) > 80) touchLockout = false; return; } }
    static bool down = false; static uint32_t seen = 0; static int lastX = 0, lastY = 0;
    if (pressed) {
        seen = now; lastX = x; lastY = y;
        if (down) return;
        down = true;
        if (page.name == "BlankView") { if (!teensyLink.running()) runScript(page.evPress, ""); updPressed = 0; return; }
        updPressed = updButtonAt(x, y); updPressedName = updButtonName(updPressed);
        if (updPressed) updRedraw = true;
        return;
    }
    if (!down || now - seen <= 80) return;
    down = false;
    const int b = updPressed; updPressed = 0;
    if (!b) return;
    updRedraw = true;
    // Lifted where it was put down, and from the button it was put on: if the panel changed under the finger
    // ("Cancel" became "Install now" as the answer arrived), nothing is pressed.
    if (updButtonAt(lastX, lastY) == b && updButtonName(b) == updPressedName) updater.press(b);
}
static void updPoll() {
    static uint32_t drawnSerial = 0, drawnBar = 0, lastBar = 0, goneAt = 0; static bool wasUp = false, lightHeld = false;
#ifdef LDRC_TEST_FALL_OVER                                // a build that falls over six seconds after every start: the boot loader's fall-back, tried out for real
    if (millis() > 6000) abort();
#endif
    if (updRequested) { updRequested = false; if (!wifiPage.showing()) updater.begin(); }
    if (rxUpdRequested) { rxUpdRequested = false; if (!wifiPage.showing()) updater.beginReceiver(); }
    updater.poll();
    const ldrc::UpdView &v = updater.view();
    const bool up = v.kind != ldrc::UpdView::NONE && topReady();
    const uint32_t barKey = v.barTotal ? (uint32_t) ((uint64_t) 1000 * min(v.barDone, v.barTotal) / v.barTotal) : 0;
    if (up) {
        if (!wasUp || v.serial != drawnSerial || updRedraw) {
            // (1.11.37, Malcolm: "when the update to the transmitter has completed, it makes no sound at all") the good
            // ending is announced: clip 104 "Update completed", once per verdict - also at the start after the screen's
            // own restart, where the verdict is shown again
            static uint32_t saidSerial = 0;
            if (v.kind == ldrc::UpdView::GOOD && v.serial != saidSerial && (v.title.rfind("Update complete", 0) == 0 || v.title.rfind("Receiver updated", 0) == 0)) { saidSerial = v.serial; audioStart(104, false); }
            { TopDraw on; updDrawPanel(v); }
            drawnSerial = v.serial; drawnBar = barKey; updRedraw = false;
            topX = UPD_X; topY = UPD_Y; topW = UPD_W; topH = UPD_H; topWho = 1; topOn = true;
            dirty(UPD_X, UPD_Y, UPD_W, UPD_H); touchPainted = true;
        } else if (v.bar && barKey != drawnBar && millis() - lastBar > 120) {
            { TopDraw on; updDrawBar(v); }
            drawnBar = barKey; lastBar = millis();
            dirty(updBarX, updBarY, updBarW, updBarH);
        }
    } else if (wasUp) { if (topWho == 1) { topOn = false; topWho = 0; } updPressed = 0; dirty(UPD_X, UPD_Y, UPD_W, UPD_H); touchPainted = true; goneAt = millis(); }   // the page, as the Teensy has drawn it meanwhile
    wasUp = up;
    // A new screen (a card with no pages on it) has nothing to show but this panel, and no button to bring it
    // back: three seconds after it has gone it comes again, unless the WiFi page is up or the pilot is flying.
    if (!up && goneAt && millis() - goneAt > 3000 && sdOk && pageNames.empty() && updater.idle() && !wifiPage.showing() && !flyingNow()) { goneAt = 0; updRequested = true; }
    // The panel has gone and no job is left: the connection to the site is given up, and its memory with it (some 50 kB).
    if (!updWifi && !updBusy && (updTls || updHttp)) { updHangUp(); delete updHttp; updHttp = nullptr; delete updTls; updTls = nullptr; }
    // While work goes on the backlight stays up whatever the Teensy's screen saver says.
    const bool hold = up && updHoldsLight();
    if (hold != lightHeld) { lightHeld = hold; if (!quietActive) backlight(hold ? 255 : sysDim * 255 / 100); }
}
static void updWeb() {
    doorOn("/update/check", HTTP_POST, []() { updRequested = true; web.send(200, "text/plain", "checking"); });
    doorOn("/update/press", HTTP_POST, []() { updater.press(web.arg("button").toInt()); web.send(200, "text/plain", "pressed"); });
    doorOn("/update/status", HTTP_GET, []() {
        auto esc = [](const std::string &t) { std::string o; for (char c : t) { if (c == '"' || c == '\\') o.push_back('\\'); if ((unsigned char) c >= 32) o.push_back(c); } return o; };
        static const char *kinds[] = { "none", "busy", "note", "offer", "working", "good", "bad", "choose" };
        const ldrc::UpdView &v = updater.view();
        std::string out = std::string("{\"screen\":\"") + SCREEN_VERSION + "\",\"kind\":\"" + kinds[v.kind] + "\",\"title\":\"" + esc(v.title) + "\",\"choices\":[";
        for (size_t i = 0; i < v.choices.size(); ++i) out += std::string(i ? "," : "") + "[\"" + esc(v.choices[i].name) + "\",\"" + esc(v.choices[i].note) + "\"," + (v.choices[i].current ? "true" : "false") + "]";
        out += "],\"rows\":[";
        for (size_t i = 0; i < v.rows.size(); ++i) out += std::string(i ? "," : "") + "[\"" + esc(v.rows[i].what) + "\",\"" + esc(v.rows[i].now) + "\",\"" + esc(v.rows[i].next) + "\"]";
        out += "],\"lines\":[";
        for (size_t i = 0; i < v.lines.size(); ++i) out += std::string(i ? "," : "") + "\"" + esc(v.lines[i]) + "\"";
        out += "],\"warning\":\"" + esc(v.warning) + "\",\"buttons\":[\"" + esc(v.button1) + "\",\"" + esc(v.button2) + "\",\"" + esc(v.button3) + "\"]";
        char n[200]; snprintf(n, sizeof n, ",\"bar\":[%lu,%lu],\"working\":%s,\"trial\":%s,\"busy\":%s,\"free_kb\":%lu,\"stack_free\":%lu,\"log\":[", (unsigned long) v.barDone, (unsigned long) v.barTotal,
                              updater.working() ? "true" : "false", updHost.onTrial() ? "true" : "false", updBusy ? "true" : "false", web.arg("free") == "1" ? (unsigned long) updHost.freeKb() : 0ul,
                              updTaskHandle ? (unsigned long) uxTaskGetStackHighWaterMark(updTaskHandle) : 0ul);      // the least the download task's stack has ever had to spare
        out += n;
        const auto &log = updater.log();
        for (size_t i = 0; i < log.size(); ++i) out += std::string(i ? "," : "") + "\"" + esc(log[i]) + "\"";
        out += "]}";
        web.send(200, "application/json", out.c_str());
    });
}
