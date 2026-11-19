#!/usr/bin/env python3
"""Reviewer A (16): the screen's dying words glued behind one of its own words that is "ended where its own text ends" (Nextion.h OwnWordCut, called at the head of
main.cpp's own-words block - in FRONT of the look for the dying words). The REAL lines of main.cpp, OwnWordCut and ScreenDyingWords (dev/test_wholepage scene_own_words)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (taken into the suite: this file's own tree)
import lib
import scene_own_words as ow
SCENES = r'''
    more(); ScreenFramesBursts = true; BoundFlag = ModelMatched = false;
    const char *dying = "Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1).";
    for (const char *head : { "", "TIME=1731672000", "UKRULES", "ldrcpipe=2", "LDRCAWAKE", "LDRCWHO" })
    {
        nowUs += 3000000; const size_t l0 = logLines.size(); std::string t = std::string(head) + dying;
        const bool answered = xText(t.c_str());
        // (THE SIXTEENTH REVIEW'S CURE: what OwnWordCut cuts away is looked at for the dying words first - behind "TIME=", "UKRULES" and "ldrcpipe=N" the log had no line)
        CHECK(logLines.size() - l0 >= 1);
        say("'%s' + the panic handler's first line, read as one: answered in the own-words block %d; lines in the log %d; what is left for the pages' words: '%.40s'\n", head, (int) answered, (int) (logLines.size() - l0), TextIn);
    }
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('dying_behind_word', SCENES, extra=ow.EXTRA, args=['--show'], label='reviewer A'))
