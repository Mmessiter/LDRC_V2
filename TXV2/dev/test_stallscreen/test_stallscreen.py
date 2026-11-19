#!/usr/bin/env python3
"""A SCREEN WHOSE LOOP STANDS STILL - what the ninth review's first reviewer found (15 Nov 2026), on the real screen's port.

The pretend screen's "stall" was not the real thing: one constant line, never cut, and no test stalled it near a page command.
dev/test_stalepress's pretend screen now carries its bytes as the real one's port does (screen.realUart: the reviewer's own
model, from the screen's source and the UART driver it is built with), and the scenes here are the reviewer's experiments, kept
with what should hold - each builds a program of its own on dev/test_noanswer's (the REAL routines over the pretend screen):
  scene_second_tap   a second tap on OK while the screen stands still for longer than the marker's wait (1.5 s): obeyed on the
                     NEXT page, and Model options' zeros saved - the fault B211 was written against. A late marker is OWED now
  scene_cut_line     the screen's "the loop is silent" line in two parts: its tail read as the head of a text reply, a page's
                     number glued behind a word taken for a box's number, the tail "FrontView" taken for the screen's restart
  scene_storms       saves, number boxes, Model options' OK, the Models page and a page still coming up, under stalls planted at
                     random - a screen up to 1.11.197 (the line in pieces, no end) and one from 1.11.198 (one piece, a newline)

... and the tenth review's (reviewer A's experiments, 15 Nov 2026):
  scene_question_before_wait   a page command from inside the wait of a question's OWN page command: the question waited on, unseen
  scene_swallowed_marker       a page a fifth of a second in coming up: its second marker and its number written BETWEEN the two pieces of
                               the screen's line, read in one go by the main loop, and lost - the new page's buttons deaf for 1.5 s
  scene_first_mark             the first page command of all: the screen is known to say markers after it, every time
  scene_board_storm            the storm with page commands of the board's own and the screen's bare words - also COLD, before the screen
                               has said a marker (102 presses on the wrong page in 20000 trials there)
  scene_half_second            half a second is a time, not a bound: the line's rest held back for longer, out with the answer
  scene_front_page             (the author's) a page being opened is overtaken by the front page - the model connects in that moment: this board
                               believed the other page, and the front page stood still. Found by the page's number; the front page afresh
  scene_rules                  rules no test held: the box's page "whatever it is"; the half minute of an answer owed; "it has started
                               again" said by the screen (0 for its session's number), not concluded from an answer that was not read

... and the eleventh review's (reviewer A's experiments 5 and 7):
  scene_zero_rules             (reviewer A's break-it round) the readers' small rules, each held by itself: "the 0 must stand right in front" in every
                               reader, a cut 0, the page's number only when due, the number said back is not the session's, a page command from
                               inside a get's radio turn
  scene_save_stall             a save under its own stall: the field screen's loop still for a quarter to two thirds of a second behind the save's
                               own queue, or behind the page a question's way back puts up - "press Save again" every time. The half second of
                               "a word with no end" is waited out before a text box is asked: every save is taken

... and the twelfth review's (reviewer A's experiments P, D / T and O8, taken as they came; his L is scene_half_second's H4):
  scene_wait_paths             the paths of a text box's wait behind a word with no end that no scene reached: the page goes, the screen starts
                               again, the settling look is not answered, a word comes out with its answer; (the author's) the look answered
                               late, and the look that finds the screen's keyboard up
  scene_unheld_rules           "a word open when the wait began is open for all of it"; the settling look's answer is ours while the model's
                               telemetry is written from inside the waits
  scene_older_screen           a page command from inside a get's radio turn, on a screen that says no markers and frames nothing: what stood
                               open is let go (scene_zero_rules' O8 is masked on a screen that says markers)

... and the thirteenth review's (reviewer A's experiment 2):
  scene_core_order             which of the screen's two cores speaks first after a hold of both: the loop's answer BEFORE the line's rest - the
                               look answered clean, the rest in front of the box's answer after all. What holds that order is the loop's own line
                               ("core 0 silent"), said in front of its answers: both orders, with that line and without

   python3 dev/test_stallscreen/test_stallscreen.py            (--show: the scenes' own account)"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
SCENES = ('scene_second_tap', 'scene_cut_line', 'scene_storms', 'scene_question_before_wait', 'scene_swallowed_marker', 'scene_first_mark', 'scene_board_storm', 'scene_half_second', 'scene_rules', 'scene_front_page', 'scene_save_stall', 'scene_zero_rules', 'scene_wait_paths', 'scene_unheld_rules', 'scene_older_screen', 'scene_core_order')

def one(s):
    r = subprocess.run([sys.executable, os.path.join(HERE, s + '.py')] + [a for a in sys.argv[1:] if a == '--show'], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return s, r.returncode, r.stdout + r.stderr

def main():
    bad = 0; checks = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for s, rc, out in ex.map(one, SCENES):
            lines = [l for l in out.split('\n') if l.strip()]
            print('\n'.join(lines if '--show' in sys.argv else [l for l in lines if l.startswith('FAIL') or l.startswith('test_stallscreen (')]))
            for l in lines:
                if l.startswith('test_stallscreen ('):
                    try: checks += int(l.split('):')[1].split()[0])
                    except (IndexError, ValueError): pass
            if rc or 'ALL GOOD' not in lines:
                bad += 1; print('FAILED: ' + s)
                if '--show' not in sys.argv: print('\n'.join(lines[-12:]))
    print('test_stallscreen: %d scene files, %d checks, %d failed' % (len(SCENES), checks, bad))
    if not bad: print('ALL GOOD')
    return 1 if bad else 0

if __name__ == '__main__': sys.exit(main())
