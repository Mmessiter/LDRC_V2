#!/usr/bin/env python3
"""NO BOX BEHIND A QUESTION THAT ANOTHER PAGE WAS PUT UP OVER (B211, the fifteenth review; reviewer B's experiment, adopted).
"Move these trims into subtrim" - its boxes, with the REAL TrimsToSubtrim, GetConfirmation, MsgBox, GetYesOrNo over the pretend screen
(scene_bank_shown_again's world).
 B1. the question answered Yes: the model saved BEFORE the "Done" box.
 B2. THE QUESTION OVERTAKEN: the model connects while "Move these trims into subtrim?" waits - the front page comes up by itself (the question is
     closed as "No": Utilities.h GetYesOrNo). TrimsToSubtrim then put up "Cancelled. Subtrim not changed." - over the front page - and its way
     back was "page TrimView": the screen on the Trim page, this board on the front page. Now: no box behind QuestionOvertaken (Model_IDs.h's
     two questions likewise - held here by their text)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
import scene_bank_shown_again as base
import re
m = lib.m
_ids = re.sub(r'//[^\n]*', '', m.release(m.src('include/Model_IDs.h'))); _trm = re.sub(r'//[^\n]*', '', base.TRM)
if len(re.findall(r'else\s*\{\s*if \(QuestionOvertaken\)\s*return;\s*MsgBox\(pModelsIDView, NotDone\);\s*\}', _ids)) != 2 or len(re.findall(r'MsgBox\(pModelsIDView, NotDone\);', _ids)) != 2 \
        or not re.search(r'else\s*\{\s*if \(QuestionOvertaken\)\s*return;\s*MsgBox\(pTrimView, ItsCancelled\);', _trm):
    print(('FAIL: ' if not os.environ.get('LDRC_RUNS_ONLY') else '(a source check, not held in this run: LDRC_RUNS_ONLY) ') + 'Trims.h TrimsToSubtrim and Model_IDs.h (both questions): behind a "No" that was another page put up over the question - QuestionOvertaken - NO box is put up (its way back put the screen on the asker\'s page, this board on the other)')
    if not os.environ.get('LDRC_RUNS_ONLY'): sys.exit(1)
_IDS = m.release(m.src('include/Model_IDs.h'))
EXTRA = base.EXTRA + m.lift(base.TRM, 'void TrimsToSubtrim()') + r'''
// ---- the Model ID page's two questions (Model_IDs.h): the REAL DeleteModelID and StoreModelID
static union { uint64_t Val64; uint8_t Val8[8]; } ModelsMacUnion, ModelsMacUnionSaved;
static char pModelsIDView[] = "page IDsStartView"; static int idsDrawn = 0;
static void DisplayStoredID() { ++idsDrawn; } static void DisplayCurrentID() { ++idsDrawn; }   // (they write the page's texts: counted)
''' + m.lift(_IDS, 'FLASHMEM void DeleteModelID()') + m.lift(_IDS, 'FLASHMEM void StoreModelID()') + r'''
static uint64_t frontAtUs = 0; static bool frontDone = false;
static void ModelConnects() { if (frontDone || nowUs < frontAtUs) return; frontDone = true; BoundFlag = ModelMatched = true; GotoFrontView(); }   // (BindNow's part that matters: the front page, by itself)
static void my24b(int n) { if (n == 75) TrimsToSubtrim(); else if (n == 76) StoreModelID(); else if (n == 178) DeleteModelID(); else more24(n); }
'''
SCENES = r'''
    // B1. Yes: moved, saved before the box
    {
        openView(TRIM_VIEW, 1, false); SendCommand((char *) "page TrimView"); loopFor(400);
        screen.pages["TrimView"].buttons["move"] = { 0x00, 75, 0x00, 0x00 }; extra24 = my24b;
        Trims[1][0] = 90; saves.clear();
        tapAt(5, "move"); tapAt(600, "yes"); tapAt(1400, "yes"); loopFor(2200);         // the question: Yes; the "Done" box: OK
        say("B1. Yes: sub trim of channel 1 now %d, its trim %d; saved %d time(s); then page %s, view %u\n", SubTrims[0] - 127, Trims[1][0], (int) saves.size(), screen.page.c_str(), (unsigned) CurrentView);
        CHECK(SubTrims[0] == 137 && Trims[1][0] == 80 && saves.size() == 1 && screen.page == "TrimView" && CurrentView == TRIM_VIEW);
    }
    // B2. the model connects while the question waits
    {
        openView(TRIM_VIEW, 1, false); SendCommand((char *) "page TrimView"); loopFor(400);
        screen.pages["TrimView"].buttons["move"] = { 0x00, 75, 0x00, 0x00 }; extra24 = my24b;
        Trims[1][0] = 90; saves.clear(); BoundFlag = ModelMatched = true;               // (a wait flies the model only while one is connected: here the link comes back)
        frontAtUs = nowUs + 700000; frontDone = false; sendDataHook = ModelConnects;
        tapAt(5, "move"); tapAt(2500, "yes"); loopFor(3500);                            // (the box that then stands there is answered 1.8 s after the front page came)
        say("B2. the model connected while the question waited: the question closed %d (overtaken %d)\n", questionsClosed, questionsOvertaken);
        loopFor(3000);
        say("    its OK pressed, three seconds on: the screen shows %s, this board believes view %u (the front page is %u, the Trim page %u); sub trim %d, trim %d, saves %d; the main loop put the front page back %d time(s)\n",
            screen.page.c_str(), (unsigned) CurrentView, (unsigned) FRONTVIEW, (unsigned) TRIM_VIEW, SubTrims[0] - 127, Trims[1][0], (int) saves.size(), frontBeliefs);
        CHECK(SubTrims[0] == 127 && Trims[1][0] == 90 && saves.empty());                // nothing was moved
        CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW && questionsOvertaken == 1);   // THE FRONT PAGE STANDS: the screen shows the page this board believes
        CHECK(screen.pages["PopupView"].boxes["Dialog"].txt.find("Cancelled") == std::string::npos);   // ... and no "Cancelled." box was ever put up over it
        sendDataHook = nullptr;
    }
    // B3, B4 (the break-it round's second look: a text check alone held these two). THE MODEL ID PAGE'S TWO QUESTIONS, each overtaken by the front page
    //     (the model connects while it waits): no "... not stored" / "... retained" box over the front page, none of the page's texts written
    //     onto it, nothing stored, nothing deleted - and answered in the ordinary way they do what they did
    for (int which = 0; which < 2; ++which)
    {
        auto idsPage = [&]() { openView(MODELIDVIEW, 1, false); Page ids; ids.id = 71; ids.buttons["store"] = { 0x00, 76, 0x00, 0x00 }; ids.buttons["delete"] = { 0x00, 178, 0x00, 0x00 };
                               screen.pages["IDsStartView"] = ids; screen.pages0 = screen.pages; SendCommand((char *) "page IDsStartView"); loopFor(400); extra24 = my24b; };
        idsPage();
        ModelsMacUnion.Val64 = 0x112233445566ull; ModelsMacUnionSaved.Val64 = which ? 0x0A0B0C0D0E0Full : 0; const uint64_t was = ModelsMacUnionSaved.Val64;
        saves.clear(); idsDrawn = 0; BoundFlag = ModelMatched = true; const int over0 = questionsOvertaken;
        frontAtUs = nowUs + 700000; frontDone = false; sendDataHook = ModelConnects;
        tapAt(5, which ? "delete" : "store"); tapAt(2500, "yes"); loopFor(3500); loopFor(3000);
        const std::string dialog = screen.pages["PopupView"].boxes["Dialog"].txt;
        say("B%d. the Model ID page's '%s' question overtaken by the front page: the screen shows %s, view %u; the ID kept %s; saves %d; the page's texts written %d\n", 3 + which, which ? "delete" : "store",
            screen.page.c_str(), (unsigned) CurrentView, ModelsMacUnionSaved.Val64 == was ? "as it was" : "CHANGED", (int) saves.size(), idsDrawn);
        CHECK(questionsOvertaken == over0 + 1 && screen.page == "FrontView" && CurrentView == FRONTVIEW && ModelsMacUnionSaved.Val64 == was && saves.empty() && idsDrawn == 0);
        CHECK(dialog.find("not stored") == std::string::npos && dialog.find("retained") == std::string::npos);
        sendDataHook = nullptr;
        // ... and answered Yes by the pilot it does what it did: stored (deleted), the model saved, its "Done" box, the page's texts drawn
        idsPage(); idsDrawn = 0; saves.clear(); BoundFlag = ModelMatched = false;
        tapAt(5, which ? "delete" : "store"); tapAt(700, "yes"); tapAt(1600, "yes"); loopFor(2800);
        CHECK(ModelsMacUnionSaved.Val64 == (which ? 0 : ModelsMacUnion.Val64) && saves.size() == 1 && idsDrawn == 2 && screen.page == "IDsStartView" && CurrentView == MODELIDVIEW);
        CHECK(screen.pages["PopupView"].boxes["Dialog"].txt.find(which ? "Model ID deleted." : "Model ID stored.") == 0);
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('trims_box', SCENES, extra=EXTRA, more_defines=('MODELIDVIEW', 'MMSAVED', 'SLOWSERVOVIEW', 'CHANNELSUSED', 'TRIM_VIEW', 'GRAPHVIEW', 'PIDVIEW', 'RFGOVERNORVIEW_PROFILE', 'PIDADVANCEDVIEW', 'RESCUEVIEW',
                                                                         'RESCUE2VIEW', 'EASYVIEW', 'ROTORFLIGHTVIEW', 'RFBACKUP_RESTOREVIEW', 'PICKBANKVIEW1', 'PICKBANKVIEW2', 'RATESVIEW_RF', 'LISTENMODE',
                                                                         'BEEPCOMPLETE', 'BEEPMIDDLE', 'CLICKZERO', 'DEFAULTTRIMREPEATSPEED')))
