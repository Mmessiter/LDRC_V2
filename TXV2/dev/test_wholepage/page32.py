#!/usr/bin/env python3
"""THE SUB-TRIM PAGE'S FILE (the screen's card: hmi/pages/32.json), WORD FOR WORD (B211, 15-16 Nov 2026).
'old': the file from before - its word "StEDIT" says nothing more, and this firmware takes NOTHING from it (Trims.h SubTrimWord).
'new': this release's (made by the screen project's hmi/subtrim_words.py) - the slider (its press, its moves, its release), Zero, "+" and "-" say
       "StEDIT", the channel, the number as it stood, the number it made, and that number again (22 bytes); a tap puts the channel's own box into
       the slider's number; the part "rs" puts the slider on the shown channel's box and says "StEDIT" and the number in "rsn", twice (14 bytes).
Anything else is an error: somebody changed the page, and the main board's rule and its tests' pretend page (scene_subtrim.py) want looking at again.

THE WHOLE FILE IS PINNED (the fourteenth review: the named parts' scripts were compared, and a page changed in ANY OTHER part - another part's script,
a page event, a new button, a timer - passed as "this release's": 11 of the reviewer's 12 changed pages would have been published beside this
firmware). PINS holds the SHA-256 of each known file's canonical JSON (keys sorted, no spaces); the named checks below it stay, to say what differs.
The pin is of the page as decoded: the file's own BYTES are held to plain ASCII from "{" before that (page_read - the fifteenth review).
A page changed on purpose (a restyle): read its diff, then put its pin here -  python3 page32.py FILE  prints it.
Used by the scenes (scene_subtrim.py, scene_subtrim_page.py, scene_subtrim_real.py) and by dev/release_v1b.py, which publishes this release's only."""
import hashlib, json, sys
PINS = {'86c9e3b7fdf2f1b555f0ff3482df230dd17c96bd492c132f1d7a0dbcb1358733': 'old',     # the field's page 32 (screens to 1.11.197)
        'e90203486584b118ad53ed3e36a3de2d4f8ccb50845747ea1d91b4c70a8734ba': 'new'}     # this release's (with screen 1.11.198)
def pin_of(p32): return hashlib.sha256(json.dumps(p32, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
def named_kind(p32, path='hmi/pages/32.json'):
    """'old' / 'new' by the parts this firmware's rule rests on - or an AssertionError that says which of them is not as known"""
    ev = {c['n']: (c.get('ev') or {}) for c in p32['comps']}; a = {c['n']: (c.get('a') or {}) for c in p32['comps']}
    names = ['n00'] + ['n%d' % k for k in range(1, 16)]
    for k, nm in enumerate(names): assert 'if(s0.val==%d)\n{\n  %s.val=n0.val\n}' % (k + 1, nm) in ev['n0']['r'], nm      # click n0,0: the chosen channel's own box = n0
    assert 'n0.val' not in ev['n0']['p']                   # ("click n0,1": the colours only)
    assert p32['ev']['preinitialize'].endswith('click n00,0')
    scopes = {c['n']: c.get('g') for c in p32['comps']}
    assert all(scopes[n] == 'g' for n in names + ['n0', 'h0']) and scopes['s0'] == 'l', scopes
    old = all(ev[nm]['r'] == 'click n0,1\ns0.val=%d\n%s.bco=WHITE\n%s.pco=RED\nprint "StCH"\nh0.val=%s.val+127' % (k + 1, nm, nm, nm) for k, nm in enumerate(names)) \
        and ev['h0']['r'] == 'n0.val=h0.val-127\nprint "StEDIT"\nclick n0,0' and ev['h0']['m'] == ev['h0']['r'] and ev['h0']['p'] == '//n0.val=h0.val-127' \
        and ev['b0']['r'] == 'n0.val+=1\nif(n0.val>127)\n{\n  n0.val=127\n}\nh0.val=n0.val+127\nprint "StEDIT"\nclick n0,0' \
        and ev['b1']['r'] == 'n0.val-=1\nif(n0.val<-127)\n{\n  n0.val=-127\n}\nh0.val=n0.val+127\nprint "StEDIT"\nclick n0,0' \
        and ev['b2']['r'] == 'n0.val=0\nh0.val=127\nclick n0,0\nprint "StEDIT"' and (a['h0'].get('minval'), a['h0'].get('maxval')) == (0, 254)
    SAY = 'print "StEDIT"\nprint s0.val\nprint n0.val\n'; TWICE = 'print n0.val\nprint n0.val\nclick n0,0'
    new = all(ev[nm]['r'] == 'click n0,1\ns0.val=%d\nn0.val=%s.val\n%s.bco=WHITE\n%s.pco=RED\nprint "StCH"\nh0.val=%s.val+127' % (k + 1, nm, nm, nm, nm) for k, nm in enumerate(names)) \
        and ev['h0']['r'] == SAY + 'n0.val=h0.val-127\n' + TWICE and ev['h0']['m'] == ev['h0']['r'] and ev['h0']['p'] == ev['h0']['r'] \
        and ev['b0']['r'] == SAY + 'n0.val+=1\nif(n0.val>117)\n{\n  n0.val=117\n}\nh0.val=n0.val+127\n' + TWICE \
        and ev['b1']['r'] == SAY + 'n0.val-=1\nif(n0.val<-117)\n{\n  n0.val=-117\n}\nh0.val=n0.val+127\n' + TWICE \
        and ev['b2']['r'] == SAY + 'n0.val=0\nh0.val=127\n' + TWICE and (a['h0'].get('minval'), a['h0'].get('maxval')) == (10, 244) \
        and ev.get('rs') == {'r': ''.join('if(s0.val==%d)\n{\n  n0.val=%s.val\n}\n' % (k + 1, nm) for k, nm in enumerate(names)) + 'h0.val=n0.val+127\nprint "StEDIT"\nprint rsn.val\nprint rsn.val'} \
        and [(c.get('t'), c.get('g')) for c in p32['comps'] if c['n'] == 'rsn'] == [('variable', 'l')] \
        and [c for c in p32['comps'] if c['n'] == 'rs'][0].get('t') == 'hotspot' and [c for c in p32['comps'] if c['n'] == 'rs'][0].get('x') == -2000
    old = old and 'rs' not in ev
    assert old != new, 'the Sub-trim page file %s is neither the one before nor this release\'s in the parts the main board\'s rule rests on: LOOK at it (the pretend page of the tests does what those two do)' % path
    return 'new' if new else 'old'
def page_read(path):
    """B211 (the fifteenth review): THE FILE IS READ AS THE SCREEN READS IT - ITS OWN BYTES. Python's json takes a byte order mark, UTF-16 and UTF-32 as they
    come; the screen's reader (ArduinoJson) cannot read any of them, and the page does not come up. The pin is of the page as DECODED: such a file was
    "this release's" (the release hands this gate the bytes; a path was read as text, and refused a mark only by chance).
    Both known files are plain ASCII from their first byte, "{": a page file is held to that - a little more than the screen asks (it reads over a
    space in front), so that nothing it cannot read gets by. Anything else: an AssertionError. The bytes are decoded HERE, as ASCII - a second
    belt: handed to json as they are, UTF-16 without a mark would be guessed and read, should its zero bytes ever get by the rule.
    A path, or the file's own bytes -> (the page, the name to call it by)"""
    raw = bytes(path) if isinstance(path, (bytes, bytearray)) else open(path, 'rb').read()
    if isinstance(path, (bytes, bytearray)): path = 'hmi/pages/32.json'
    odd = [k for k, c in enumerate(raw) if not (32 <= c < 127 or c in (9, 10, 13))]            # (plain text: the printable ASCII, tab, newline, return)
    if raw[:1] != b'{' or odd:
        what = 'it is empty' if not raw else 'it begins with a byte order mark' if raw[:3] == b'\xef\xbb\xbf' or raw[:2] in (b'\xff\xfe', b'\xfe\xff') \
            else 'the byte at %d is 0x%02X' % (odd[0], raw[odd[0]]) if odd else 'it begins with %r' % raw[:1].decode()
        raise AssertionError('the Sub-trim page file %s is not plain ASCII text from its first byte, "{" (%s): the screen cannot read a byte order mark or UTF-16 '
                             '- save it as plain text' % (path, what))
    return json.loads(raw.decode('ascii')), path
def page_kind(path):
    """a path, or the file's own bytes: 'old' or 'new' - the WHOLE file one of the two that are pinned. Anything else: an AssertionError"""
    p32, path = page_read(path)
    pin = pin_of(p32); kind = PINS.get(pin)
    if kind is None:
        try: by_name = named_kind(p32, path)
        except Exception as e: by_name = 'neither (%s)' % (str(e)[:160] or type(e).__name__)
        raise AssertionError('the Sub-trim page file %s is not one of the two this firmware knows WORD FOR WORD (its pin %s). By the parts the rule rests on it is: %s - so something ELSE in it was changed, '
                             'or those parts were. Read its diff against the known file; a change made on purpose gets its pin in dev/test_wholepage/page32.py' % (path, pin, by_name))
    assert named_kind(p32, path) == kind, 'the Sub-trim page file %s has the pin of the %s one and is not it by its parts: page32.py itself is wrong' % (path, kind)
    return kind
if __name__ == '__main__':
    for f in sys.argv[1:]:
        try: p = page_read(f)[0]
        except AssertionError as e: print(f, '\n   NOT A PAGE FILE AS THE SCREEN READS ONE -', str(e)); continue
        print(f, '\n   pin', pin_of(p), '\n   known as', PINS.get(pin_of(p), 'NOT KNOWN'))
        try: print('   by its named parts:', named_kind(p, f))
        except Exception as e: print('   by its named parts: neither -', str(e)[:200])
