// B50: the main board's own line to the receiver over the screen's Bluetooth pipe (screen 1.11.18), for the Rotorflight
// settings the parameter packets never carried (rescue, servos, travel, filters, the ESC): the receiver's raw
// Rotorflight line, /api/msp?fn=N[&data=HEX], which its own pages use. "ldrcreq <id> <path>" goes to the screen,
// "ldrcrep <id> <code> <body>\n" comes back; the body of a read is the reply's bytes as hex. One request at a time, never
// waited for: a page's state machine asks, goes on, and looks for the reply each time round (PipeReplyReady).
#include <Arduino.h>
#include "1Definitions.h"
#ifndef PIPE_HTTP_H
#define PIPE_HTTP_H

static int PipeReqId = 0;            // the last request's id
static int PipeRepId = -1;           // the reply in hand is to this request (-1: none)
static int PipeRepCode = 0;          // its HTTP code (0 = the screen could not ask: not joined, no answer)
static char PipeRepBody[1600];       // its body
static uint32_t PipeReqSentMs = 0;

int PipeRequest(const char *path)
{
    ++PipeReqId;
    if (PipeReqId > 30000)
        PipeReqId = 1;
    char b[400];
    snprintf(b, sizeof(b), "ldrcreq %d %s", PipeReqId, path);
    SendCommand(b);
    PipeReqSentMs = millis();
    PipeRepId = -1;
    return PipeReqId;
}
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return millis() - PipeReqSentMs > 9000; } // the screen gives a request 6 s, and the receiver's own line waits up to a second or two
void PipeReplyFromScreen(const char *text) // "<id> <code> <body>" (up to the line's end)
{
    char *e = nullptr;
    const long id = strtol(text, &e, 10);
    if (e == text)
        return;
    const long code = strtol(e, &e, 10);
    while (*e == ' ')
        ++e;
    size_t n = 0;
    while (e[n] && e[n] != '\n' && e[n] != '\r' && n < sizeof(PipeRepBody) - 1)
        ++n;
    memcpy(PipeRepBody, e, n);
    PipeRepBody[n] = 0;
    PipeRepCode = (int)code;
    PipeRepId = (int)id;
}
// A Rotorflight request: fn, and the bytes to send with it (none for a read).
int MspAsk(uint8_t fn, const uint8_t *data, int len)
{
    char path[360];
    int n = snprintf(path, sizeof(path), "/api/msp?fn=%u", (unsigned)fn);
    if (data && len > 0)
    {
        n += snprintf(path + n, sizeof(path) - n, "&data=");
        for (int i = 0; i < len && n < (int)sizeof(path) - 3; ++i)
            n += snprintf(path + n, sizeof(path) - n, "%02x", data[i]);
    }
    return PipeRequest(path);
}
// The reply's hex into bytes; how many.
int PipeReplyBytes(uint8_t *out, int max)
{
    int n = 0;
    const char *p = PipeRepBody;
    while (p[0] && p[1] && n < max)
    {
        char h[3] = {p[0], p[1], 0};
        char *e = nullptr;
        const long v = strtol(h, &e, 16);
        if (e != h + 2)
            break;
        out[n++] = (uint8_t)v;
        p += 2;
    }
    return n;
}
#endif
