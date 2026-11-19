#!/usr/bin/env python3
"""A PAGE'S FIELDS ARE TAKEN WHOLE, OR NOT AT ALL - and the rest of what the ninth review of B211 found (15 Nov 2026).

The scenes here are the ninth review's own experiments, kept as they were written (each says what went wrong and what should
hold), now run against the cures. Each file builds a program of its own on dev/test_noanswer's (the REAL routines lifted out
of the headers over the pretend screen):
  scene_filters_level   the Rotorflight Filters and Level pages: "no answer" for a field read as 0, held to its range - and
                        written to the flight controller (Save, and a touch on a field; one "which page?" answer lost)
  scene_beeper          OK with unsaved edits gathered the page with no look at "was every box answered?", and put it back as
                        if typed: "Please press Save again" then wiped the model's name in the flight controller
  scene_governor        a refused governor Save wrote 255s into the bytes a save ALREADY UNDER WAY was about to send
  scene_motorbox_view   the box "The motor switch is ON" went back with a bare "page FrontView" while this board believed the
                        Models page: the page's own look at its list loaded model 1 by itself
  scene_answer          the pilot's "No", written over by a box put up in the 20 ms behind the question's way back
  scene_question_stall  a screen that stands still for a few seconds under a question; "Save now?" closed by itself is not Discard
  scene_goback          a question another page came over does not send its own way back over that page

... and the tenth review's (reviewer B's experiments, 15 Nov 2026):
  scene_pageback        a page's own word ("ldrcadj") obeyed while a question box was up read the page's boxes FROM THE BOX'S PAGE:
                        the knob's row became zeros. Not obeyed while a question waits; and no page box has an answer inside one
  scene_batgather       the Battery sensors page's gather kept the wrong thing whole (what it writes: the two sensors' settings)
  scene_saveagain       "Please press Save again" - and the page had been drawn afresh from what was in hand: what he typed was gone
  scene_switchflip      a tap whose gather lost a box "does nothing" - but the screen's own switch had flipped: drawn as in hand
  scene_logline         the log names the FIRST box that had no answer, and says how many more
  scene_closeditself    "Save now?" closed by this board, read as Discard after a box came up in its way back's wait
  scene_question_gap    a page put up in the 20 ms between a question's own page command and the start of its wait
  scene_pagegone_goback the page taken away under a save: the save's "no answer" box does not put the save's page back up
  scene_question_latemark   the question's own page marker comes late (a screen standing still 1.6 to 4 s)
  scene_question_restart    the screen starts again under a question and every sign of it is lost
  scene_twoquestions    two questions in one button's work, taps at random moments, a screen standing still now and then
  scene_blackbox        the Black box page: what was typed stays after a refused Save and after a tap that lost a box (as scene_saveagain
                        and scene_switchflip have it for the Level and Filters pages)
  scene_rfsettings      the Rotorflight settings page (gear ratio, ARMING CHANNEL, rates follow banks): its three boxes whole, or not
                        at all - one could be taken and the next not, the model saved so (found by the check of what a gather writes)

... and the eleventh review's (reviewer B's experiments, and what followed from them):
  scene_subtrim         the Sub-trim page: A CHANGE IS TAKEN ONLY WHEN IT STARTS FROM WHAT THE MODEL HAS - the page's word says its channel, the
                        number as it stood and the number it made (the thirteenth review: three cures that asked the page afterwards each
                        stored another channel's number by some road); a screen a quarter second behind, the page come back from a box, a
                        finger resting on the slider, words never heard or not kept, the page file from before, every byte of the burst
  scene_models_memory   a list of all the models was sent - a wait that flies the model - before the pilot's own model was read back
                        (the Models page's list, the IDs report)
  scene_typed_stays     what was typed stays on the page where no gather stands in front of a box: Battery's Save refused, Calibrate,
                        the black box's Erase (scene_beeper has Beeper & name's Save; scene_pageback the knobs page that came back undrawn)
  scene_small_rules     the screen's own word ended where its text ends; the save / restore dialog; the governor page's words; the file
                        name's question overtaken in its wait for the name; the Models page's look with the page's number still to come;
                        the Easy page's sliders before a save
  scene_older_gathers   (the twelfth review) gathers the source check could not see, made whole: "FailSAVE" (the mixture went to the receiver as the
                        failsafe set), the failsafe page's way out, "RXBAT", the bank names
  scene_subtrim_doors16 (the sixteenth review, reviewer B's own) Z1: a touch's burst that comes on ANOTHER page still says what kind of page file said it; Y0, Y1:
                        a fresh writing-out begins OK's count of "clicks once more" afresh.
  scene_subtrim_second_marker (reviewer A's own) the page's SECOND marker lost: a touch let go between the markers owes the page its writing-out.
  scene_subtrim_door_storm (reviewer A's own) THE DOORS OF OK AT RANDOM: a putting-right on its way, the screen still for 0.3 to 6 s, OK one to four times as it
                        wakes; Help's way back with a marker lost - every OK press tagged, what is saved is what the page showed at the press obeyed.
  scene_subtrim_storm_b, scene_subtrim_real_b (reviewer B's own mixes of the two storms: more OKs, long stalls, lost "done"s; seed 77123456 broke I5 once).
  scene_log_forced_writing (reviewer A's own) the log's writing forced by a full store, in the air, is the 24 short lines only.
  scene_dying_behind_word (reviewer A's own) the screen's dying words glued behind "TIME=", "UKRULES", "ldrcpipe=N": kept for the log.
  scene_subtrim_roads17 (the seventeenth review, reviewer A's own) P0, P1: a touch's burst that was KEPT and is purged with its page says what kind of page file
                        said it; Q0, Q1: every new click of this board's has its own two chances (a change not taken behind a spent count).
  scene_log_behind_word (reviewer A's own) a line for the log glued behind "TIME=", "UKRULES", "ldrcpipe=N" goes to the log before the cut.
  scene_log_held_lines  (reviewer A's own) the screen's held lines through forced writings in flight, and two restarts of the screen in one flight (28 places).
  scene_idle_off        (the eighteenth review, reviewer A's own) the power-off for idleness BY A RUN of the real routine: why off, the kept lines, the timing report,
                        the crumb, the cut - everything on the card before the pin goes up, in one opening (a text check alone held it).
  scene_log_behind_word18 (reviewer A's own) the line for the log behind an own word: logged ONCE, the word in front still served, held while the model may fly.
  scene_button_off      (the nineteenth review, reviewer A's finding 4) the power BUTTON's power-off BY A RUN of the real Close_TX_Down: the kept lines are on the
                        card before the pin goes up - with no model connected and the log switched off too (a text check alone held it).
  scene_subtrim_storm   (the author's) the Sub-trim page used at random - taps, the slider, "+" and "-", unheard touches, lost writes, stalls, another model
                        read under it, a screen up to 0.4 s behind, a hand's spacing, two channels, the page put up again, a finger resting on
                        the slider, the loop held elsewhere: the model never holds a number the pilot did not make on that channel; nothing
                        lost, page and model agree; one touch puts a channel right; from the page file before, nothing; nothing waits
  scene_slow_servo      (the twelfth review) the Slow-servo page's speeds, whole - by its own count (the bank switch reads them from the main loop), and
                        said; every bank of a model with six (banks 5 and 6 were never taken)
  scene_jobs_end        (the twelfth review, reviewer B's own) what was typed, at the END of the job a box started: Calibrate and the black box's
                        Erase run to their ends by the real polls - the typed values still stand, and Save writes them
  scene_subtrim_page    (the author's) the pretend Sub-trim page of scene_subtrim and its storm held, step for step, against the card's own page file run by
                        the screen's own interpreter - the page file from before, and this release's
  scene_own_words       (the thirteenth review) the screen's own words as main.cpp answers them, in front of the pages' words: a text that begins
                        "LDRC" and is no whole word goes no further ("LDRCLOGpMark 2" marked the GPS position); a line of the Bluetooth pipe is
                        answered before its body is searched for a page's word
  scene_bank_shown_again (the thirteenth review, what the released code already had) the motor switch is no bank change: GetBank forced "the bank
                        that was" to 254, and BankHasChanged treated every page as left for another bank - the Slow-servo page lost what was
                        typed, the Rotorflight pages read again over their edits; the trims of banks 5 and 6 (a table of five banks indexed by
                        six; "Move these trims into subtrim"); and the trims' kin
  scene_save_fails      (the fourteenth review, his own scene) what is typed while a SAVE runs is not wiped when the save fails: the Battery page with a
                        step refused, he types on - and the draws of Basics, Rescue, the Filters and Easy tuning under "keep what was typed"

  scene_subtrim_real    (the fourteenth review, reviewer A's own) THE REAL Sub-trim page file run by the screen's own interpreter under the screen's own
                        touch rules (a finger on the slider: press, moves, release) against the real Trims.h - scenes and a storm; OK at any moment

  scene_kept_lines      (the fourteenth review, the reviewers' two runs) the lines kept for a quiet moment: the restart's two lines together or neither;
                        the same note again behind a writing; THE SCREEN'S OWN LINES held whole while the model may fly (they went to the card at once)
  scene_kept_copies     (the fourteenth review, reviewer B's run; the released code had it) the kept Rotorflight copies of banks 5 and 6 never
                        reached the card, and their mark did: no copy of those banks is marked, shown or said "kept"; the read clears them
  scene_long_pipe       (the fourteenth review, reviewer A's two runs; the released code had it) a line of the Bluetooth pipe longer than the reader
                        behind a send can keep was cut and handed on as whole: dropped whole now, and said; the empty framed burst read there

   python3 dev/test_wholepage/test_wholepage.py            (--show: the scenes' own account)"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
SCENES = ('scene_filters_level', 'scene_beeper', 'scene_governor', 'scene_motorbox_view', 'scene_answer', 'scene_question_stall', 'scene_goback',
          'scene_pageback', 'scene_batgather', 'scene_saveagain', 'scene_switchflip', 'scene_logline', 'scene_closeditself', 'scene_question_gap',
          'scene_pagegone_goback', 'scene_question_latemark', 'scene_question_restart', 'scene_twoquestions', 'scene_rfsettings', 'scene_blackbox',
          'scene_subtrim', 'scene_models_memory', 'scene_typed_stays', 'scene_small_rules', 'scene_older_gathers', 'scene_jobs_end', 'scene_slow_servo', 'scene_subtrim_storm', 'scene_own_words', 'scene_subtrim_page', 'scene_bank_shown_again', 'scene_save_fails', 'scene_subtrim_real', 'scene_kept_lines', 'scene_kept_copies', 'scene_long_pipe',
          'scene_subtrim_doors', 'scene_subtrim_roads', 'scene_subtrim_real_roads', 'scene_travel_dir', 'scene_rescue_switch', 'scene_stale_block', 'scene_trims_box', 'scene_read_fails',   # (the fifteenth review: the reviewers' experiments, adopted)
          'scene_subtrim_doors16', 'scene_subtrim_second_marker', 'scene_subtrim_door_storm', 'scene_subtrim_storm_b', 'scene_subtrim_real_b', 'scene_log_forced_writing', 'scene_dying_behind_word',   # (the sixteenth review's, adopted)
          'scene_subtrim_roads17', 'scene_log_behind_word', 'scene_log_held_lines',   # (the seventeenth review's, reviewer A's own, adopted)
          'scene_idle_off', 'scene_log_behind_word18',   # (the eighteenth review's, reviewer A's own, adopted)
          'scene_button_off')   # (the nineteenth review: the power button's road by a run)

def one(s):
    r = subprocess.run([sys.executable, os.path.join(HERE, s + '.py')] + [a for a in sys.argv[1:] if a == '--show'], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return s, r.returncode, r.stdout + r.stderr

def main():
    bad = 0; checks = 0; notrun = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for s, rc, out in ex.map(one, SCENES):
            lines = [l for l in out.split('\n') if l.strip()]
            print('\n'.join(lines if '--show' in sys.argv else [l for l in lines if l.startswith('FAIL') or l.startswith('test_wholepage (')]))
            for l in lines:
                if l.startswith('test_wholepage ('):
                    try: checks += int(l.split('):')[1].split()[0])
                    except (IndexError, ValueError): pass
            if not rc and any(l.startswith('NOT RUN:') for l in lines):
                # (the fifteenth review: a scene that needs the screen project beside this one, and did not find it, SAYS so - it is counted, and the
                #  release's gate, dev/test_release_gate.py, does not pass with one not run)
                notrun.append(s); print('\n'.join(l for l in lines if l.startswith('NOT RUN:')))
            elif rc or 'ALL GOOD' not in lines:
                bad += 1; print('FAILED: ' + s)
                if '--show' not in sys.argv: print('\n'.join(lines[-12:]))
    print('test_wholepage: %d scene files, %d checks, %d failed%s' % (len(SCENES), checks, bad, ', %d NOT RUN (%s)' % (len(notrun), ', '.join(notrun)) if notrun else ''))
    if not bad: print('ALL GOOD' if not notrun else 'ALL GOOD - but for the %d scene(s) that did not run' % len(notrun))
    return 1 if bad else 0

if __name__ == '__main__': sys.exit(main())
