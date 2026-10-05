// The front page, as the flight screen reads it (lib/LdrcFlight): the page itself while it is on the glass (what is
// shown and what is hidden), else the screen's copy of what the main board last wrote to it. Shared by the screen
// (src/flight_device.h) and the Mac renderer (hmi/render_host).
#pragma once
#include "LdrcFlight.h"

struct ScreenFront : public ldrc::FlightSource {
    Comp *live(const char *c) { return page.name == "FrontView" ? find(c) : nullptr; }
    const Kept *keptOf(const char *c) { auto k = kept.find(std::string("FrontView.") + c); return k == kept.end() ? nullptr : &k->second; }
    bool shown(const char *c) override { if (Comp *p = live(c)) return p->vis; return keptOf(c) != nullptr; }
    std::string text(const char *c) override {
        if (Comp *p = live(c)) return p->txt;
        const Kept *k = keptOf(c); if (!k) return std::string();
        auto t = k->txts.find("txt"); return t == k->txts.end() ? std::string() : t->second;
    }
    long number(const char *c, long dflt) override {
        if (Comp *p = live(c)) return p->val;
        const Kept *k = keptOf(c); if (!k) return dflt;
        auto t = k->ints.find("val"); return t == k->ints.end() ? dflt : t->second;
    }
    long attribute(const char *c, const char *attr, long dflt) override {   // a colour the main board wrote: live, else as kept
        if (Comp *p = live(c)) { const std::string a = attr; return a == "bco" ? p->bco : a == "pco" ? p->pco : dflt; }
        const Kept *k = keptOf(c); if (!k) return dflt;
        auto t = k->ints.find(attr); return t == k->ints.end() ? dflt : t->second;
    }
    bool linked() override {                               // the main board's word; one too old to say: the link bar showing
        if (txStatus >= 0) return (txStatus & TX_MODEL) != 0;
        Comp *q = live("Quality"); return q && q->vis;
    }
    bool flying() override { return tx.armed; }        // its rule: the radios are off (from a main board too old to say, the front page's "Motor is ON")
};
