#!/usr/bin/env python3
"""A LIST OF ALL THE MODELS IS BUILT WITH ANOTHER MODEL IN THIS BOARD'S MEMORY - AND A WAIT THAT FLIES THE MODEL (the eleventh review, reviewer B's
experiment 5; released code had it). MenuOptions.h LoadModelSelector (the Models page's list) and Model_IDs.h CheckAllModelIds (the IDs report)
read every model slot in turn into the live memory, SENT what they had made of it - and every send waits, flying a connected model: the sticks
read, the channels worked out from whatever model is in memory, a packet sent - and only THEN read the pilot's own model back. For those
waits the connected model was flown from the settings of the LAST slot read, whatever model that is.
What must hold: every wait that flies the model, inside either routine, is made with the pilot's own model in memory.
The REAL LoadModelSelector, CheckAllModelIds, SendOtherText and EndSend; the harness's ReadOneModel says which slot is in memory, and the wait's
"fly" hook notes it. (The wait INSIDE ReadOneModel itself - 300 ms when the models file would not open - is dev/test_modelmemory's.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
MENU = m.release(m.src('include/MenuOptions.h')); IDS = m.release(m.src('include/Model_IDs.h'))
EXTRA = r'''
static std::vector<int> flownWith;              // the model slot whose settings were in this board's memory at each wait that flies the model
struct { uint64_t Val64; } ModelsMacUnionSaved = { 1 };
static uint32_t ModelBackupCrc = 0, ModelContentCrc = 0;
''' + m.lift(m.NEXTION, 'void SendOtherText(char *tbox, char *NewWord)') + m.lift(MENU, 'void LoadModelSelector()') + m.lift(IDS, 'FLASHMEM void CheckAllModelIds()') + r'''
static void noteFlight() { flownWith.push_back(modelsRead.empty() ? -1 : modelsRead.back()); }
static bool onlyWith(int slot) { for (int v : flownWith) if (v != slot) return false; return true; }
'''
SCENES = r'''
    // M1. the Models page's list, the pilot's model (number 2) connected
    more();
    { Page p; p.id = 15; p.boxes["MMems"] = { false, 0, "" }; p.boxes["modelname"] = { true, 0, "" }; screen.pages["ModelsView"] = p; screen.pages0 = screen.pages; }
    SendCommand((char *) "page ModelsView"); CurrentView = MODELSVIEW; loopFor(600);
    ModelNumber = 2; modelsRead.clear(); ReadOneModel(2); BoundFlag = ModelMatched = true;
    flownWith.clear(); flyHook = noteFlight;
    LoadModelSelector();
    flyHook = nullptr;
    say("M1. the Models page's list built with model 2 connected: waits that fly the model inside it: %d; made from model slot:", (int) flownWith.size()); for (int v : flownWith) say(" %d", v);
    say("; slots read: %d; afterwards model %d is in memory (ModelNumber %d)\n", (int) modelsRead.size(), modelsRead.back(), (int) ModelNumber);
    CHECK(flownWith.size() >= 1);                                                // (the list's send waits, flying the model)
    CHECK(onlyWith(2));                                                          // the model is never flown from another model's settings
    CHECK((int) modelsRead.size() == MAXMODELNUMBER + 1 && modelsRead.back() == 2 && ModelNumber == 2);   // (every slot read for the list, then the pilot's own back)
    loopFor(300);
    CHECK(screen.pages["ModelsView"].boxes["MMems"].val == 1);                   // (the list stands on the pilot's model: row 1)
    // M2. the IDs report (Model_IDs.h), the same
    more();
    { Page p; p.id = 16; p.boxes["MMems"] = { false, 0, "" }; p.boxes["t1"] = { true, 0, "" }; screen.pages["IDsView"] = p; screen.pages0 = screen.pages; }
    ModelNumber = 2; modelsRead.clear(); ReadOneModel(2); BoundFlag = ModelMatched = true;
    flownWith.clear(); flyHook = noteFlight;
    CheckAllModelIds();
    flyHook = nullptr;
    say("M2. the IDs report built with model 2 connected: waits that fly the model inside it: %d; made from model slot:", (int) flownWith.size()); for (int v : flownWith) say(" %d", v);
    say("; afterwards model %d is in memory (ModelNumber %d)\n", modelsRead.back(), (int) ModelNumber);
    CHECK(flownWith.size() >= 2 && onlyWith(2) && modelsRead.back() == 2 && ModelNumber == 2);
    loopFor(300);
    CHECK(!screen.pages["IDsView"].boxes["t1"].txt.empty());                     // (the report's summary was written)
    BoundFlag = ModelMatched = false;
'''
sys.exit(lib.build_run('models_memory', SCENES, extra=EXTRA, more_defines=('MODELSVIEW', 'MAXMODELNUMBER', 'IDCHECKVIEW')))
