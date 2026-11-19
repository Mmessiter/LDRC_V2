#!/usr/bin/env python3
"""A LINE OF THE BLUETOOTH PIPE LONGER THAN THE READER BEHIND A SEND CAN KEEP (the fourteenth review, reviewer A's 12 - his run, taken into the suite;
the released code had it; 16 Nov 2026). "ldrcrep <id> <code> <body>\n": the body of a read is the flight controller's bytes as hex, and the screen
passes up to 1500 characters. Nextion.h StashPendingEventBytes - the reader behind every send, in front of every get and page command - keeps 512
bytes of a frame; the bytes of a longer line were let go, its newline with them: the line never ended, and at the next FF FF FF its first 509 bytes
were handed on as a whole line (a reply's body, cut) and the frame behind it was swallowed.
 L1 a line the reader can keep is kept whole, and the page's marker behind it is read as a marker;
 L2 A LONGER LINE IS DROPPED WHOLE - nothing of it is handed on - said in the log, and the marker behind it is still read;
 L3 one whose newline never comes is dropped too.
And (reviewer A's 8, a line that had no test): the screen's empty framed burst read by that same reader makes this board strict.
The REAL Nextion.h over the pretend screen."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
SCENES = r"""
    for (int len : { 120, 400, 505, 510, 511, 512, 513, 520, 900, 1500 })
      for (int behind = 0; behind < 3; ++behind)
      {
        more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
        std::string line = "ldrcrep 12 200 "; while ((int) line.size() < len - 1) line += "0123456789ABCDEF"[line.size() % 16]; line += "\n";
        std::vector<uint8_t> b(line.begin(), line.end());
        const std::vector<uint8_t> marker = { 'q', 0x34, 0x12, 0x45, 0x4C, 0xFF, 0xFF, 0xFF };          // a page's marker (4C451234), as a reply stands behind a line
        const std::string next = "ldrctel 1,2,3\n";                                                        // ... or the pipe's next line
        if (behind == 0) b.insert(b.end(), marker.begin(), marker.end());
        if (behind == 1) b.insert(b.end(), next.begin(), next.end());
        const uint16_t long0 = PipeLinesTooLong, drop0 = PendingDropped; const size_t log0 = logLines.size(); ScreenSaysMarks = false; nowUs += 3000000;
        screen.emit(nowUs + 100, b); nowUs += 30000;
        SendText((char *) "t0", (char *) "x");                                                             // any write of this board's: GetReturnCode -> StashPendingEventBytes
        const bool fits = len <= 510;                                                                      // (the store of kept frames holds 510 bytes of one: PendingPush)
        const bool tooLong = len >= 513;                                                                   // (the reader's own buffer is 512: 511 and 512 are read whole, and find no room in the store - counted there, as ever)
        std::string kept(PendingEvent, PendingEvent + PendingEventLen);
        if (len == 120 || len == 511 || len == 513 || len == 1500 || !(fits ? kept.find(line) == 0 : kept.find("ldrcrep") == std::string::npos))
            say("L. a pipe line of %4d bytes read by the reader behind a send (%s behind it): %d frame(s) kept for the main loop (%d bytes), dropped as too long %u, the marker read %d, said in the log %d\n",
                (int) line.size(), behind == 0 ? "a page's marker" : behind == 1 ? "the pipe's next line" : "nothing", (int) PendingCount, (int) PendingEventLen, (unsigned) (uint16_t) (PipeLinesTooLong - long0), (int) ScreenSaysMarks, (int) (logLines.size() - log0));
        if (fits) { CHECK(PendingCount >= 1 && PendingLens[0] == line.size() && kept.compare(0, line.size(), line) == 0 && PipeLinesTooLong == long0 && logLines.size() == log0); }   // L1: whole, as it came
        else { CHECK(kept.find("ldrcrep") == std::string::npos && kept.find("0123456789") == std::string::npos && (uint16_t) (PipeLinesTooLong - long0) == (tooLong ? 1 : 0));           // L2: NOTHING of it is handed on
               if (tooLong) CHECK(logLines.size() == log0 + 1 && logLines.back().find("longer than 511 bytes") != std::string::npos && PendingDropped == drop0);
               else CHECK((uint16_t) (PendingDropped - drop0) == 1); }                                                                                                                         // (511, 512: no room in the store - counted there)
        if (behind == 0) CHECK(ScreenSaysMarks);                                                           // the marker behind it is read as a marker, whatever the line's length
        if (behind == 1)
        {   // ... and the pipe's next line is a frame of its own (kept when the store has room behind the first: 510 bytes in all)
            const bool room = !fits || line.size() + next.size() < 511;
            CHECK((kept.find(next) != std::string::npos) == room && PendingCount == (fits ? 1 : 0) + (room ? 1 : 0));
        }
        if (behind == 2) CHECK(PendingCount == (fits ? 1 : 0));
        screen.deaf = false; holdCatchUp = false;
      }
    // L3. the long line's newline never comes (the screen stopped in the middle of it): nothing of it is kept - and it is said
    {
        more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
        std::string line = "ldrcrep 12 200 "; while (line.size() < 700) line += "0123456789ABCDEF"[line.size() % 16];
        const uint16_t long0 = PipeLinesTooLong; nowUs += 3000000;
        screen.emit(nowUs + 100, std::vector<uint8_t>(line.begin(), line.end())); nowUs += 60000;
        SendText((char *) "t0", (char *) "x");
        CHECK(PendingCount == 0 && (uint16_t) (PipeLinesTooLong - long0) == 1);
        // ... while the model may fly: a short line, kept for a quiet moment (no card write)
        mayFly = true; nowUs += 3000000; const size_t log0 = logLines.size();
        std::string l2 = line + "\n"; screen.emit(nowUs + 100, std::vector<uint8_t>(l2.begin(), l2.end())); nowUs += 60000; SendText((char *) "t0", (char *) "x");
        CHECK((uint16_t) (PipeLinesTooLong - long0) == 2 && logLines.size() == log0 + 1 && logLines.back() == "(kept for later) Pipe line over 511 bytes: dropped");
        mayFly = false; screen.deaf = false; holdCatchUp = false;
    }
    // L4 (the fifteenth review, reviewer A's X4: no test held it). ONLY A LINE OF THE PIPE IS DROPPED TO ITS NEWLINE. Any other frame longer than the
    //    reader keeps - a text's answer of 600 bytes - ends at its own FF FF FF as it always did, and the frame behind it is read: with "any frame too
    //    long is dropped to the next newline" a page's marker behind it, and everything up to some later newline, would be swallowed
    {
        more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; holdCatchUp = true;
        std::vector<uint8_t> b = { 'p' }; for (int i = 0; i < 600; ++i) b.push_back((uint8_t) ('a' + i % 26)); b.push_back(0xFF); b.push_back(0xFF); b.push_back(0xFF);
        const std::vector<uint8_t> marker = { 'q', 0x34, 0x12, 0x45, 0x4C, 0xFF, 0xFF, 0xFF };
        b.insert(b.end(), marker.begin(), marker.end());
        const uint16_t long0 = PipeLinesTooLong; const size_t log0 = logLines.size(); ScreenSaysMarks = false; nowUs += 3000000;
        screen.emit(nowUs + 100, b); nowUs += 60000;
        SendText((char *) "t0", (char *) "x");
        say("L4. a text's answer of 600 bytes and a page's marker behind it: dropped as a pipe line %u, the marker read %d, said in the log %d\n", (unsigned) (uint16_t) (PipeLinesTooLong - long0), (int) ScreenSaysMarks, (int) (logLines.size() - log0));
        CHECK(PipeLinesTooLong == long0 && ScreenSaysMarks && logLines.size() == log0);
        // (his 11) ... and a pipe line that IS dropped ends "right behind a 0": a whole value reply of 0, the long line, then the next frame
        ScreenZeroJustSaid = true; std::string line = "ldrcrep 12 200 "; while (line.size() < 700) line += "0123456789ABCDEF"[line.size() % 16]; line += "\n";
        nowUs += 3000000; screen.emit(nowUs + 100, std::vector<uint8_t>(line.begin(), line.end())); nowUs += 60000; SendText((char *) "t0", (char *) "x");
        CHECK((uint16_t) (PipeLinesTooLong - long0) == 1 && !ScreenZeroJustSaid);
        screen.deaf = false; holdCatchUp = false;
    }
    // (reviewer A's 8) THE SCREEN'S ANSWER TO "ldrcframe=1" - an empty framed burst - READ BY THE READER BEHIND A SEND: this board is strict from that moment
    {
        more(); ScreenFramesBursts = false; screen.deaf = true;
        screen.emit(nowUs + 100, { 0x7E, 0x7E, 0x04, 0x00, 0, 0, 0, 0 }); nowUs += 5000;
        SendText((char *) "t0", (char *) "x");
        say("the screen's empty framed burst read by the reader behind a send: this board knows the screen frames its bursts: %d\n", (int) ScreenFramesBursts);
        CHECK(ScreenFramesBursts);
        screen.deaf = false;
    }
"""
if __name__ == '__main__':
    sys.exit(lib.build_run('long_pipe', SCENES, extra=''))
