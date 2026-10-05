// NextionScript.cpp — see NextionScript.h for the language notes.
#include "NextionScript.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// ---------------------------------------------------------------- constants
enum { T_INT = 0, T_STR, T_REF, T_OP, T_LP, T_RP };
enum { R_SYS = 0, R_COMP };
enum { CN_CMP = 0, CN_AND, CN_OR };
enum { K_ASSIGN = 0, K_IF, K_LOOP, K_JUMP, K_CMD };
enum { C_UNKNOWN = 0, C_PRINT, C_PRINTS, C_PRINTH, C_CLICK, C_VIS, C_PAGE, C_BTLEN, C_COVX, C_SUBSTR, C_PLAY };
enum { B_IF = 0, B_ELSE, B_WHILE, B_FOR };
// operator codes: single chars for arithmetic, letters for the two-char operators
// 'L' <<   'R' >>   'e' ==   'n' !=   'l' <=   'g' >=   'A' &&   'O' ||
static const int MAX_DEPTH = 8;

struct ColourName { const char* name; int32_t value; };
static const ColourName kColours[] = {
    { "WHITE", 65535 }, { "BLACK", 0 }, { "RED", 63488 }, { "GREEN", 2016 },
    { "BLUE", 31 }, { "GRAY", 33840 }, { "YELLOW", 65504 }, { "BROWN", 48192 },
};

// ---------------------------------------------------------------- helpers
typedef NextionScript::Value Value;
typedef NextionScript::Tok Tok;
typedef NextionScript::Expr Expr;
typedef NextionScript::Ref Ref;
typedef NextionScript::Cond Cond;
typedef NextionScript::Stmt Stmt;
typedef NextionScript::Block Block;

static bool isIdStart(char c) { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_'; }
static bool isIdChar(char c) { return isIdStart(c) || (c >= '0' && c <= '9'); }
static bool isDigit(char c) { return c >= '0' && c <= '9'; }
static bool isSpace(char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }

static std::string trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && isSpace(s[a])) a++;
    while (b > a && isSpace(s[b - 1])) b--;
    return s.substr(a, b - a);
}

static bool startsWith(const std::string& s, const char* p) {
    size_t n = strlen(p);
    return s.size() >= n && s.compare(0, n, p) == 0;
}

// keyword followed by '(' or whitespace or '{' (so `ifx.val=1` is not `if`)
static bool isKeyword(const std::string& s, const char* kw) {
    size_t n = strlen(kw);
    if (!startsWith(s, kw)) return false;
    if (s.size() == n) return true;
    char c = s[n];
    return c == '(' || c == ' ' || c == '\t' || c == '{';
}

// cut a // comment that is outside quotes
static std::string stripComment(const std::string& s) {
    bool q = false;
    for (size_t i = 0; i < s.size(); i++) {
        char c = s[i];
        if (q) { if (c == '\\' && i + 1 < s.size()) i++; else if (c == '"') q = false; }
        else if (c == '"') q = true;
        else if (c == '/' && i + 1 < s.size() && s[i + 1] == '/') return s.substr(0, i);
    }
    return s;
}

// find `needle` outside quotes / parentheses / brackets
static size_t findTop(const std::string& s, const char* needle, size_t from = 0) {
    size_t n = strlen(needle);
    int depth = 0; bool q = false;
    for (size_t i = from; i < s.size(); i++) {
        char c = s[i];
        if (q) { if (c == '\\' && i + 1 < s.size()) i++; else if (c == '"') q = false; continue; }
        if (c == '"') { q = true; continue; }
        if (c == '(' || c == '[') depth++;
        else if (c == ')' || c == ']') depth--;
        else if (depth == 0 && s.compare(i, n, needle) == 0) return i;
    }
    return std::string::npos;
}

static void splitTop(const std::string& s, const char* sep, std::vector<std::string>& out) {
    out.clear();
    size_t n = strlen(sep), from = 0;
    for (;;) {
        size_t p = findTop(s, sep, from);
        if (p == std::string::npos) { out.push_back(trim(s.substr(from))); return; }
        out.push_back(trim(s.substr(from, p - from)));
        from = p + n;
    }
}

// index of the bracket matching s[open] (s[open] is '(' or '['), or npos
static size_t matchBracket(const std::string& s, size_t open) {
    char o = s[open], c = (o == '(') ? ')' : ']';
    int depth = 0; bool q = false;
    for (size_t i = open; i < s.size(); i++) {
        char ch = s[i];
        if (q) { if (ch == '\\' && i + 1 < s.size()) i++; else if (ch == '"') q = false; continue; }
        if (ch == '"') q = true;
        else if (ch == o) depth++;
        else if (ch == c) { if (--depth == 0) return i; }
    }
    return std::string::npos;
}

static std::string intToStr(int32_t v) {
    char buf[16];
    snprintf(buf, sizeof buf, "%ld", (long)v);
    return std::string(buf);
}

static int32_t strToInt(const std::string& s, int base = 10) {
    const char* p = s.c_str();
    while (isSpace(*p)) p++;
    if (base == 10 && p[0] == '0' && (p[1] == 'x' || p[1] == 'X')) base = 16;
    return (int32_t)strtol(p, 0, base);
}

static Value ival(int32_t v) { Value r; r.isStr = false; r.i = v; return r; }
static Value sval(const std::string& s) { Value r; r.isStr = true; r.i = 0; r.s = s; return r; }
static int32_t toInt(const Value& v) { return v.isStr ? strToInt(v.s) : v.i; }
static std::string toStr(const Value& v) { return v.isStr ? v.s : intToStr(v.i); }

// one binary operation, Nextion style
static Value apply(const Value& a, uint8_t op, const Value& b) {
    if (op == 'A') return ival((toInt(a) != 0 && toInt(b) != 0) ? 1 : 0);
    if (op == 'O') return ival((toInt(a) != 0 || toInt(b) != 0) ? 1 : 0);
    if (a.isStr || b.isStr) {
        switch (op) {
            case '+': return sval(toStr(a) + toStr(b));
            case '-': if (a.isStr && !b.isStr) {   // "abc"-=1 drops the last character (the keyboard's DEL key)
                          std::string t = a.s; size_t n = b.i < 0 ? 0 : (size_t)b.i; if (n > t.size()) n = t.size(); t.erase(t.size() - n); return sval(t); }
                      break;
            case 'e': return ival(toStr(a) == toStr(b) ? 1 : 0);
            case 'n': return ival(toStr(a) != toStr(b) ? 1 : 0);
            case '<': return ival(toStr(a) <  toStr(b) ? 1 : 0);
            case '>': return ival(toStr(a) >  toStr(b) ? 1 : 0);
            case 'l': return ival(toStr(a) <= toStr(b) ? 1 : 0);
            case 'g': return ival(toStr(a) >= toStr(b) ? 1 : 0);
            default: break;   // fall through to int arithmetic on the converted values
        }
    }
    int32_t x = toInt(a), y = toInt(b);
    uint32_t ux = (uint32_t)x, uy = (uint32_t)y;
    switch (op) {
        case '+': return ival((int32_t)(ux + uy));
        case '-': return ival((int32_t)(ux - uy));
        case '*': return ival((int32_t)(ux * uy));
        case '/': return ival(y == 0 ? 0 : (y == -1 ? (int32_t)(0u - ux) : x / y));
        case '%': return ival(y == 0 ? 0 : (y == -1 ? 0 : x % y));
        case '&': return ival(x & y);
        case '|': return ival(x | y);
        case '^': return ival(x ^ y);
        case 'L': return ival((y < 0 || y >= 32) ? 0 : (int32_t)(ux << y));
        case 'R': return ival((y < 0 || y >= 32) ? 0 : (x >> y));
        case 'e': return ival(x == y ? 1 : 0);
        case 'n': return ival(x != y ? 1 : 0);
        case '<': return ival(x <  y ? 1 : 0);
        case '>': return ival(x >  y ? 1 : 0);
        case 'l': return ival(x <= y ? 1 : 0);
        case 'g': return ival(x >= y ? 1 : 0);
        default:  return ival(0);
    }
}

static void putLE32(uint8_t* out, int32_t v) {
    uint32_t u = (uint32_t)v;
    out[0] = (uint8_t)u; out[1] = (uint8_t)(u >> 8); out[2] = (uint8_t)(u >> 16); out[3] = (uint8_t)(u >> 24);
}

// ---------------------------------------------------------------- NextionHost defaults
std::string NextionHost::pageNameById(int32_t id) { return intToStr(id); }
std::string NextionHost::compNameById(const std::string& page, int32_t id) { (void)page; return "b" + intToStr(id); }

// ---------------------------------------------------------------- NextionScript: setup
static Stmt makeStmt(uint8_t kind, int line) {
    Stmt s; s.kind = kind; s.op = 0; s.cmd = 0; s.ref = -1; s.expr = -1; s.jump = -1; s.line = line;
    return s;
}

NextionScript::NextionScript(NextionHost& host, const std::string& currentPage)
    : host_(host), page_(currentPage), errLine_(0), maxSteps_(200000), lastChainValid_(false) {
    lastChain_.kind = B_IF; lastChain_.openIdx = -1; lastChain_.awaitingBrace = false;
    lastChain_.hasStep = false; lastChain_.step = makeStmt(K_ASSIGN, 0);
}

bool NextionScript::fail(int line, const std::string& msg) {
    err_ = msg; errLine_ = line;
    return false;
}

// ---------------------------------------------------------------- compile
bool NextionScript::compile(const std::string& code) {
    stmts_.clear(); exprs_.clear(); refs_.clear(); conds_.clear();
    err_.clear(); errLine_ = 0; lastChainValid_ = false;
    std::vector<Block> stack;
    size_t pos = 0; int lineNo = 0;
    bool ok = true;
    while (pos <= code.size() && ok) {
        size_t nl = code.find('\n', pos);
        std::string line = code.substr(pos, nl == std::string::npos ? std::string::npos : nl - pos);
        lineNo++;
        ok = parseLine(line, lineNo, stack);
        if (nl == std::string::npos) break;
        pos = nl + 1;
    }
    if (ok && !stack.empty()) ok = fail(lineNo, stack.back().awaitingBrace ? "expected '{'" : "unclosed block");
    if (!ok) stmts_.clear();
    return ok;
}

bool NextionScript::parseLine(const std::string& raw, int lineNo, std::vector<Block>& stack) {
    std::string line = trim(stripComment(raw));
    if (line.empty()) return true;

    if (!stack.empty() && stack.back().awaitingBrace) {
        if (line == "{") { stack.back().awaitingBrace = false; return true; }
        return fail(lineNo, "expected '{' after if/else/while/for");
    }
    if (line == "{") return fail(lineNo, "unexpected '{'");

    bool chainStillValid = false;

    if (line[0] == '}') {
        std::string rest = trim(line.substr(1));
        if (stack.empty()) return fail(lineNo, "unexpected '}'");
        Block b = stack.back(); stack.pop_back();
        int here = (int)stmts_.size();
        if (rest.empty()) {
            switch (b.kind) {
                case B_IF:
                    stmts_[b.openIdx].jump = here;
                    for (size_t i = 0; i < b.pendingElse.size(); i++) stmts_[b.pendingElse[i]].jump = here;
                    lastChain_ = b; lastChainValid_ = true; chainStillValid = true;
                    break;
                case B_ELSE:
                    for (size_t i = 0; i < b.pendingElse.size(); i++) stmts_[b.pendingElse[i]].jump = here;
                    break;
                case B_FOR:
                    if (b.hasStep) stmts_.push_back(b.step);
                    // fall through
                case B_WHILE: {
                    Stmt j = makeStmt(K_JUMP, lineNo); j.jump = b.openIdx; stmts_.push_back(j);
                    stmts_[b.openIdx].jump = (int)stmts_.size();
                    break;
                }
            }
        } else if (isKeyword(rest, "else")) {
            if (b.kind != B_IF) return fail(lineNo, "else without if");
            if (!parseOpener(rest, lineNo, stack)) return false;
        } else {
            return fail(lineNo, "unexpected text after '}'");
        }
        if (!rest.empty()) {
            // `}else…`: re-open the block just closed.  parseOpener pushed a fresh Block for the
            // else/else-if; graft the closed IF's bookkeeping onto it.
            Block& nb = stack.back();
            int k = nb.openIdx - 1;                  // the JUMP emitted before the else body
            stmts_[b.openIdx].jump = k + 1;
            nb.pendingElse = b.pendingElse; nb.pendingElse.push_back(k);
        }
    } else if (isKeyword(line, "else")) {
        if (!lastChainValid_) return fail(lineNo, "else without if");
        Block b = lastChain_;
        // the IF's false-jump currently points at stmts_.size(); it must skip the ELSE jump
        if (!parseOpener(line, lineNo, stack)) return false;
        Block& nb = stack.back();
        int k = nb.openIdx - 1;
        stmts_[b.openIdx].jump = k + 1;
        nb.pendingElse = b.pendingElse; nb.pendingElse.push_back(k);
    } else if (isKeyword(line, "if") || isKeyword(line, "while") || isKeyword(line, "for")) {
        if (!parseOpener(line, lineNo, stack)) return false;
    } else {
        Stmt st = makeStmt(K_ASSIGN, lineNo);
        bool isAssign = false;
        if (!parseAssign(line, lineNo, st, isAssign)) return false;
        if (!isAssign && !parseCommand(line, lineNo, st)) return false;
        stmts_.push_back(st);
    }
    if (!chainStillValid) lastChainValid_ = false;
    return true;
}

// if(…) / while(…) / for(…;…;…) / else / else if(…)   — pushes a Block, emits the header stmts
bool NextionScript::parseOpener(const std::string& body, int lineNo, std::vector<Block>& stack) {
    std::string s = body;
    bool brace = true;
    if (!s.empty() && s[s.size() - 1] == '{') { s = trim(s.substr(0, s.size() - 1)); brace = false; }

    Block b; b.kind = B_IF; b.openIdx = -1; b.awaitingBrace = brace; b.hasStep = false;
    b.step = makeStmt(K_ASSIGN, lineNo);

    if (isKeyword(s, "else")) {
        Stmt j = makeStmt(K_JUMP, lineNo); stmts_.push_back(j);        // patched at chain end
        std::string tail = trim(s.substr(4));
        if (tail.empty()) {
            b.kind = B_ELSE; b.openIdx = (int)stmts_.size();            // openIdx-1 is the JUMP
            stack.push_back(b);
            return true;
        }
        if (!isKeyword(tail, "if")) return fail(lineNo, "expected 'if' or '{' after else");
        s = tail;   // fall into the if handling; openIdx will be the IF (JUMP is at openIdx-1)
    }

    const char* kw = isKeyword(s, "if") ? "if" : (isKeyword(s, "while") ? "while" : "for");
    std::string inner = trim(s.substr(strlen(kw)));
    if (inner.empty() || inner[0] != '(') return fail(lineNo, std::string("expected '(' after ") + kw);
    size_t close = matchBracket(inner, 0);
    if (close == std::string::npos || trim(inner.substr(close + 1)).size() != 0)
        return fail(lineNo, std::string("unbalanced parentheses in ") + kw);
    inner = inner.substr(1, close - 1);

    if (kw[0] == 'f') {
        std::vector<std::string> parts;
        splitTop(inner, ";", parts);
        if (parts.size() != 3) return fail(lineNo, "for needs init;cond;step");
        if (!parts[0].empty()) {
            Stmt init = makeStmt(K_ASSIGN, lineNo); bool ia = false;
            if (!parseAssign(parts[0], lineNo, init, ia)) return false;
            if (!ia) return fail(lineNo, "for init must be an assignment");
            stmts_.push_back(init);
        }
        b.kind = B_FOR; b.openIdx = (int)stmts_.size();
        Stmt loop = makeStmt(K_LOOP, lineNo);
        if (!parts[1].empty() && !parseCond(parts[1], lineNo, loop.expr, 0)) return false;
        stmts_.push_back(loop);
        if (!parts[2].empty()) {
            bool sa = false;
            if (!parseAssign(parts[2], lineNo, b.step, sa)) return false;
            if (!sa) return fail(lineNo, "for step must be an assignment");
            b.hasStep = true;
        }
        stack.push_back(b);
        return true;
    }

    b.kind = (kw[0] == 'w') ? B_WHILE : B_IF;
    b.openIdx = (int)stmts_.size();
    Stmt st = makeStmt(b.kind == B_WHILE ? K_LOOP : K_IF, lineNo);
    if (!parseCond(inner, lineNo, st.expr, 0)) return false;
    stmts_.push_back(st);
    stack.push_back(b);
    return true;
}

// end of ref-like text: ident ( [ … ] )? ( . ident ( [ … ] )? )*
static size_t scanRefEnd(const std::string& s) {
    size_t p = 0;
    for (;;) {
        if (p >= s.size() || !isIdStart(s[p])) return 0;
        while (p < s.size() && isIdChar(s[p])) p++;
        if (p < s.size() && s[p] == '[') {
            size_t m = matchBracket(s, p);
            if (m == std::string::npos) return 0;
            p = m + 1;
        }
        if (p < s.size() && s[p] == '.') { p++; continue; }
        return p;
    }
}

bool NextionScript::parseAssign(const std::string& s, int lineNo, Stmt& st, bool& isAssign) {
    isAssign = false;
    size_t e = scanRefEnd(s);
    if (e == 0) return true;
    size_t p = e;
    while (p < s.size() && isSpace(s[p])) p++;
    if (p >= s.size()) return true;
    std::string rest = s.substr(p);
    uint8_t op = 0; size_t opLen = 0; bool incdec = false;
    if (rest == "++") { op = '+'; incdec = true; }
    else if (rest == "--") { op = '-'; incdec = true; }
    else if (startsWith(rest, "<<=")) { op = 'L'; opLen = 3; }
    else if (startsWith(rest, ">>=")) { op = 'R'; opLen = 3; }
    else if (rest.size() >= 2 && rest[1] == '=' && strchr("+-*/%&|^", rest[0]) && rest[0] != 0) { op = (uint8_t)rest[0]; opLen = 2; }
    else if (rest[0] == '=' && (rest.size() == 1 || rest[1] != '=')) { op = '='; opLen = 1; }
    else return true;   // not an assignment (e.g. a command whose first word looks like a ref)

    isAssign = true;
    st.kind = K_ASSIGN; st.op = op;
    if (!parseRefOnly(s.substr(0, e), true, lineNo, st.ref)) return false;
    if (incdec) {
        Expr one; Tok t; t.t = T_INT; t.op = 0; t.i = 1; t.ref = -1; one.push_back(t);
        exprs_.push_back(one); st.expr = (int)exprs_.size() - 1;
    } else {
        std::string rhs = trim(rest.substr(opLen));
        if (rhs.empty()) return fail(lineNo, "missing value after '='");
        if (!parseExpr(rhs, lineNo, st.expr)) return false;
    }
    if (refs_[st.ref].kind == R_SYS) st.text = s;   // raw line for the unknownCommand fallback
    return true;
}

bool NextionScript::parseCommand(const std::string& s, int lineNo, Stmt& st) {
    st.kind = K_CMD; st.cmd = C_UNKNOWN; st.text = s;
    size_t sp = 0;
    while (sp < s.size() && !isSpace(s[sp])) sp++;
    std::string verb = s.substr(0, sp);
    std::string rest = trim(s.substr(sp));
    std::vector<std::string> a;
    if (!rest.empty()) splitTop(rest, ",", a);

    struct { const char* name; uint8_t id; size_t minArgs; } const table[] = {
        { "print", C_PRINT, 1 }, { "prints", C_PRINTS, 1 }, { "printh", C_PRINTH, 0 },
        { "click", C_CLICK, 2 }, { "vis", C_VIS, 2 }, { "page", C_PAGE, 1 },
        { "btlen", C_BTLEN, 2 }, { "strlen", C_BTLEN, 2 }, { "covx", C_COVX, 3 }, { "cov", C_COVX, 2 },
        { "substr", C_SUBSTR, 4 }, { "play", C_PLAY, 1 },
    };
    uint8_t cmd = C_UNKNOWN; size_t minArgs = 0;
    for (size_t i = 0; i < sizeof table / sizeof table[0]; i++)
        if (verb == table[i].name) { cmd = table[i].id; minArgs = table[i].minArgs; break; }
    if (cmd == C_UNKNOWN) return true;   // routed to host.unknownCommand at run time
    if (a.size() < minArgs) return fail(lineNo, verb + " needs " + intToStr((int32_t)minArgs) + " argument(s)");
    st.cmd = cmd;
    int idx;
    switch (cmd) {
        case C_PRINTH: {
            std::string bytes;
            size_t i = 0;
            while (i < rest.size()) {
                while (i < rest.size() && isSpace(rest[i])) i++;
                if (i >= rest.size()) break;
                size_t j = i;
                while (j < rest.size() && !isSpace(rest[j])) j++;
                std::string tok = rest.substr(i, j - i);
                if (tok.size() > 2 || tok.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos)
                    return fail(lineNo, "printh: bad hex byte '" + tok + "'");
                bytes.push_back((char)strtol(tok.c_str(), 0, 16));
                i = j;
            }
            st.text = bytes;
            return true;
        }
        case C_CLICK: case C_VIS:
            if (!parseRefOnly(a[0], false, lineNo, idx)) return false;
            st.args.push_back(idx);
            if (!parseExpr(a[1], lineNo, idx)) return false;
            st.args.push_back(idx);
            return true;
        case C_PAGE:
            if (isDigit(a[0][0]) || a[0].find('.') != std::string::npos) {
                if (!parseExpr(a[0], lineNo, idx)) return false;
                st.args.push_back(idx); st.text.clear();
            } else st.text = a[0];
            return true;
        case C_BTLEN: case C_COVX: case C_SUBSTR:     // src expr, dest ref [, expr, expr]
            if (!parseExpr(a[0], lineNo, idx)) return false;
            st.args.push_back(idx);
            if (!parseRefOnly(a[1], true, lineNo, idx)) return false;
            st.args.push_back(idx);
            if (cmd == C_BTLEN) return true;
            for (size_t i = 2; i < 4; i++) {
                if (i < a.size()) { if (!parseExpr(a[i], lineNo, idx)) return false; }
                else idx = -1;
                st.args.push_back(idx);
            }
            return true;
        default:   // print, prints, play: every argument is an expression
            for (size_t i = 0; i < a.size(); i++) {
                if (!parseExpr(a[i], lineNo, idx)) return false;
                st.args.push_back(idx);
            }
            return true;
    }
}

bool NextionScript::parseRefOnly(const std::string& s, bool needAttr, int lineNo, int& idx) {
    size_t pos = 0;
    std::string t = trim(s);
    if (!parseRef(t, pos, needAttr, lineNo, idx)) return false;
    if (pos != t.size()) return fail(lineNo, "bad reference '" + t + "'");
    return true;
}

bool NextionScript::parseRef(const std::string& s, size_t& pos, bool needAttr, int lineNo, int& idx) {
    std::string names[3]; int exprs[3] = { -1, -1, -1 }; int n = 0;
    for (;;) {
        bool numeric = !needAttr && n == 0 && pos < s.size() && isDigit(s[pos]);   // `vis 255,1`
        if (!numeric && (pos >= s.size() || !isIdStart(s[pos]))) return fail(lineNo, "expected a name in '" + s + "'");
        if (n == 3) return fail(lineNo, "too many dots in '" + s + "'");
        size_t st = pos;
        while (pos < s.size() && (numeric ? isDigit(s[pos]) : isIdChar(s[pos]))) pos++;
        names[n] = s.substr(st, pos - st);
        if (pos < s.size() && s[pos] == '[') {
            size_t m = matchBracket(s, pos);
            if (m == std::string::npos) return fail(lineNo, "unbalanced '[' in '" + s + "'");
            if (!parseExpr(s.substr(pos + 1, m - pos - 1), lineNo, exprs[n])) return false;
            pos = m + 1;
        }
        n++;
        if (pos < s.size() && s[pos] == '.') { pos++; continue; }
        break;
    }
    Ref r; r.kind = R_COMP; r.pageExpr = -1; r.compExpr = -1;
    if (needAttr) {
        if (n == 1) { if (exprs[0] >= 0) return fail(lineNo, "bad variable '" + s + "'"); r.kind = R_SYS; r.comp = names[0]; }
        else if (n == 2) { r.comp = names[0]; r.compExpr = exprs[0]; r.attr = names[1]; }
        else { r.page = names[0]; r.pageExpr = exprs[0]; r.comp = names[1]; r.compExpr = exprs[1]; r.attr = names[2]; }
        if (n > 1 && exprs[n - 1] >= 0) return fail(lineNo, "attribute cannot be indexed in '" + s + "'");
    } else {
        if (n == 1) { r.comp = names[0]; r.compExpr = exprs[0]; }
        else if (n == 2) { r.page = names[0]; r.pageExpr = exprs[0]; r.comp = names[1]; r.compExpr = exprs[1]; }
        else return fail(lineNo, "expected page.component in '" + s + "'");
    }
    refs_.push_back(r);
    idx = (int)refs_.size() - 1;
    return true;
}

bool NextionScript::parseExpr(const std::string& src, int lineNo, int& idx) {
    std::string s = trim(src);
    Expr e;
    size_t pos = 0; bool wantOperand = true; int depth = 0;
    while (pos < s.size()) {
        char c = s[pos];
        Tok t; t.t = T_INT; t.op = 0; t.i = 0; t.ref = -1;
        if (isSpace(c)) { pos++; continue; }
        if (c == '"') {
            size_t i = pos + 1;
            for (; i < s.size(); i++) {
                if (s[i] == '\\' && i + 1 < s.size() && s[i + 1] == '"') { t.s.push_back('"'); i++; }
                else if (s[i] == '"') break;
                else t.s.push_back(s[i]);
            }
            if (i >= s.size()) return fail(lineNo, "unterminated string");
            pos = i + 1; t.t = T_STR; wantOperand = false;
        } else if (c == '(') {
            if (++depth > MAX_DEPTH) return fail(lineNo, "expression too deeply nested");
            t.t = T_LP; pos++; wantOperand = true;
        } else if (c == ')') {
            if (--depth < 0) return fail(lineNo, "unbalanced ')'");
            t.t = T_RP; pos++; wantOperand = false;
        } else if (wantOperand && (isDigit(c) || (c == '-' && pos + 1 < s.size() && isDigit(s[pos + 1])))) {
            size_t i = pos + 1;
            while (i < s.size() && isIdChar(s[i])) i++;
            std::string num = s.substr(pos, i - pos);
            bool neg = num[0] == '-'; if (neg) num = num.substr(1);
            bool hex = num.size() > 2 && num[0] == '0' && (num[1] == 'x' || num[1] == 'X');
            if (num.find_first_not_of(hex ? "0123456789abcdefABCDEFxX" : "0123456789") != std::string::npos)
                return fail(lineNo, "bad number '" + num + "'");
            uint32_t u = (uint32_t)strtoul(num.c_str() + (hex ? 2 : 0), 0, hex ? 16 : 10);
            t.i = (int32_t)(neg ? 0u - u : u);
            pos = i; wantOperand = false;
        } else if (wantOperand && isIdStart(c)) {
            size_t e2 = pos; while (e2 < s.size() && isIdChar(s[e2])) e2++;
            bool colour = false;
            if (e2 >= s.size() || (s[e2] != '.' && s[e2] != '[')) {
                std::string name = s.substr(pos, e2 - pos);
                for (size_t k = 0; k < sizeof kColours / sizeof kColours[0]; k++)
                    if (name == kColours[k].name) { t.i = kColours[k].value; colour = true; break; }
            }
            if (colour) pos = e2;
            else { t.t = T_REF; if (!parseRef(s, pos, true, lineNo, t.ref)) return false; }
            wantOperand = false;
        } else if (!wantOperand) {
            const char* two[] = { "<<", ">>", "==", "!=", "<=", ">=", "&&", "||" };
            const char twoCode[] = { 'L', 'R', 'e', 'n', 'l', 'g', 'A', 'O' };
            t.t = T_OP;
            size_t k = 0;
            for (; k < 8; k++) if (s.compare(pos, 2, two[k]) == 0) { t.op = (uint8_t)twoCode[k]; pos += 2; break; }
            if (k == 8) {
                if (!strchr("+-*/%&|^<>", c)) return fail(lineNo, std::string("unexpected '") + c + "' in expression");
                t.op = (uint8_t)c; pos++;
            }
            wantOperand = true;
        } else {
            return fail(lineNo, std::string("unexpected '") + c + "' in expression");
        }
        e.push_back(t);
    }
    if (depth != 0) return fail(lineNo, "unbalanced '('");
    if (e.empty() || wantOperand) return fail(lineNo, "incomplete expression '" + s + "'");
    exprs_.push_back(e);
    idx = (int)exprs_.size() - 1;
    return true;
}

// cond := or-list of and-lists of comparisons; parentheses group
bool NextionScript::parseCond(const std::string& src, int lineNo, int& idx, int depth) {
    if (depth > MAX_DEPTH) return fail(lineNo, "condition too deeply nested");
    std::string s = trim(src);
    while (!s.empty() && s[0] == '(' && matchBracket(s, 0) == s.size() - 1) s = trim(s.substr(1, s.size() - 2));
    if (s.empty()) return fail(lineNo, "empty condition");
    Cond c; c.kind = CN_CMP; c.cmp = 0; c.l = -1; c.r = -1;
    std::vector<std::string> parts;
    splitTop(s, "||", parts);
    if (parts.size() == 1) splitTop(s, "&&", parts); else c.kind = CN_OR;
    if (parts.size() > 1) {
        if (c.kind != CN_OR) c.kind = CN_AND;
        for (size_t i = 0; i < parts.size(); i++) {
            int k;
            if (!parseCond(parts[i], lineNo, k, depth + 1)) return false;
            c.kids.push_back(k);
        }
        conds_.push_back(c); idx = (int)conds_.size() - 1;
        return true;
    }
    // single comparison: first top-level comparison operator, skipping << and >>
    size_t p = std::string::npos; uint8_t cmp = 0; size_t len = 0;
    {
        int d = 0; bool q = false;
        for (size_t i = 0; i < s.size() && p == std::string::npos; i++) {
            char ch = s[i];
            if (q) { if (ch == '\\') i++; else if (ch == '"') q = false; continue; }
            if (ch == '"') { q = true; continue; }
            if (ch == '(' || ch == '[') d++; else if (ch == ')' || ch == ']') d--;
            if (d != 0) continue;
            char nx = i + 1 < s.size() ? s[i + 1] : 0;
            if (ch == '=' && nx == '=') { p = i; cmp = 'e'; len = 2; }
            else if (ch == '!' && nx == '=') { p = i; cmp = 'n'; len = 2; }
            else if (ch == '<' && nx == '=') { p = i; cmp = 'l'; len = 2; }
            else if (ch == '>' && nx == '=') { p = i; cmp = 'g'; len = 2; }
            else if (ch == '<' && nx != '<') { p = i; cmp = '<'; len = 1; }
            else if (ch == '>' && nx != '>') { p = i; cmp = '>'; len = 1; }
            else if ((ch == '<' || ch == '>') && nx == ch) i++;   // shift operator
        }
    }
    if (p == std::string::npos) {
        if (!parseExpr(s, lineNo, c.l)) return false;
    } else {
        c.cmp = cmp;
        if (!parseExpr(s.substr(0, p), lineNo, c.l)) return false;
        if (!parseExpr(s.substr(p + len), lineNo, c.r)) return false;
    }
    conds_.push_back(c); idx = (int)conds_.size() - 1;
    return true;
}

// ---------------------------------------------------------------- run
bool NextionScript::run(const std::string& code, const std::string& selfComp) {
    if (!compile(code)) return false;
    return runCompiled(selfComp);
}

bool NextionScript::runCompiled(const std::string& selfComp) {
    self_ = selfComp;
    err_.clear(); errLine_ = 0;
    return execute();
}

bool NextionScript::execute() {
    size_t pc = 0; uint32_t steps = 0;
    while (pc < stmts_.size()) {
        if (++steps > maxSteps_) return fail(stmts_[pc].line, "runaway loop in " + (self_.empty() ? page_ : page_ + "." + self_));
        const Stmt& s = stmts_[pc];
        switch (s.kind) {
            case K_ASSIGN: doAssign(s); pc++; break;
            case K_IF: case K_LOOP:
                if (s.expr < 0 || evalCond(s.expr, 0)) pc++; else pc = (size_t)s.jump;
                break;
            case K_JUMP: pc = (size_t)s.jump; break;
            default: doCommand(s); pc++; break;
        }
    }
    return true;
}

bool NextionScript::resolveRef(int idx, std::string& page, std::string& comp, std::string& attr, bool& isSys) {
    const Ref& r = refs_[idx];
    isSys = r.kind == R_SYS;
    if (isSys) { comp = r.comp; return true; }
    page = r.pageExpr >= 0 ? host_.pageNameById(toInt(evalExpr(r.pageExpr))) : (r.page.empty() ? page_ : r.page);
    comp = r.compExpr >= 0 ? host_.compNameById(page, toInt(evalExpr(r.compExpr))) : r.comp;
    attr = r.attr;
    return true;
}

Value NextionScript::readRef(int idx) {
    std::string page, comp, attr; bool isSys;
    resolveRef(idx, page, comp, attr, isSys);
    if (isSys) return ival(host_.getSys(comp));
    if (attr == "txt") return sval(host_.getTxt(page, comp));
    return ival(host_.getInt(page, comp, attr));
}

void NextionScript::writeRef(int idx, const Value& v, const Stmt& st) {
    std::string page, comp, attr; bool isSys;
    resolveRef(idx, page, comp, attr, isSys);
    if (isSys) {
        if (comp == "delay") host_.delayMs((uint32_t)toInt(v));
        else if (!host_.setSys(comp, toInt(v))) host_.unknownCommand(st.text);
        return;
    }
    if (attr == "txt") host_.setTxt(page, comp, toStr(v));
    else host_.setInt(page, comp, attr, toInt(v));
}

Value NextionScript::evalExpr(int idx) {
    size_t pos = 0;
    return evalTokens(exprs_[idx], pos, 0);
}

// left to right, no precedence (as the Nextion does); parentheses via bounded recursion
Value NextionScript::evalTokens(const Expr& e, size_t& pos, int depth) {
    Value acc = ival(0);
    bool first = true; uint8_t op = 0;
    while (pos < e.size()) {
        const Tok& t = e[pos];
        if (t.t == T_RP) { pos++; return acc; }
        if (t.t == T_OP) { op = t.op; pos++; continue; }
        Value v;
        if (t.t == T_INT) { v = ival(t.i); pos++; }
        else if (t.t == T_STR) { v = sval(t.s); pos++; }
        else if (t.t == T_REF) { v = readRef(t.ref); pos++; }
        else { pos++; v = (depth < MAX_DEPTH) ? evalTokens(e, pos, depth + 1) : ival(0); }
        if (first) { acc = v; first = false; } else acc = apply(acc, op, v);
    }
    return acc;
}

bool NextionScript::evalCond(int idx, int depth) {
    const Cond& c = conds_[idx];
    if (c.kind == CN_CMP) {
        Value l = evalExpr(c.l);
        if (c.cmp == 0) return toInt(l) != 0;
        return toInt(apply(l, c.cmp, evalExpr(c.r))) != 0;
    }
    if (depth > MAX_DEPTH) return false;
    for (size_t i = 0; i < c.kids.size(); i++) {
        bool b = evalCond(c.kids[i], depth + 1);
        if (c.kind == CN_AND && !b) return false;
        if (c.kind == CN_OR && b) return true;
    }
    return c.kind == CN_AND;
}

void NextionScript::doAssign(const Stmt& st) {
    Value v = evalExpr(st.expr);
    if (st.op != '=') v = apply(readRef(st.ref), st.op, v);
    writeRef(st.ref, v, st);
}

static std::string formatInt(int32_t v, int32_t len, int32_t fmt) {
    std::string s;
    if (fmt == 2) { char b[12]; snprintf(b, sizeof b, "%lX", (unsigned long)(uint32_t)v); s = b; }
    else {
        s = intToStr(v);
        if (fmt == 1) {   // currency: thousands separators
            bool neg = s[0] == '-'; std::string d = neg ? s.substr(1) : s, out;
            for (size_t i = 0; i < d.size(); i++) { if (i && (d.size() - i) % 3 == 0) out.push_back(','); out.push_back(d[i]); }
            s = neg ? "-" + out : out;
        }
    }
    while (len > 0 && (int32_t)s.size() < len) s.insert(s[0] == '-' ? 1 : 0, "0");
    return s;
}

void NextionScript::doCommand(const Stmt& st) {
    uint8_t buf[4];
    switch (st.cmd) {
        case C_PRINT: {
            Value v = evalExpr(st.args[0]);
            if (v.isStr) host_.send((const uint8_t*)v.s.data(), v.s.size());
            else { putLE32(buf, v.i); host_.send(buf, 4); }
            break;
        }
        case C_PRINTS: {
            Value v = evalExpr(st.args[0]);
            int32_t len = st.args.size() > 1 ? toInt(evalExpr(st.args[1])) : 0;
            if (v.isStr) host_.send((const uint8_t*)v.s.data(), (len <= 0 || (size_t)len > v.s.size()) ? v.s.size() : (size_t)len);
            else { putLE32(buf, v.i); host_.send(buf, (len <= 0 || len > 4) ? 4 : (size_t)len); }
            break;
        }
        case C_PRINTH:
            if (!st.text.empty()) host_.send((const uint8_t*)st.text.data(), st.text.size());
            break;
        case C_CLICK: case C_VIS: {
            std::string page, comp, attr; bool isSys;
            resolveRef(st.args[0], page, comp, attr, isSys);
            bool on = toInt(evalExpr(st.args[1])) != 0;
            if (st.cmd == C_CLICK) host_.click(page, comp, on); else host_.vis(page, comp, on);
            break;
        }
        case C_PAGE:
            if (!st.text.empty()) host_.gotoPage(st.text);
            else host_.gotoPage(host_.pageNameById(toInt(evalExpr(st.args[0]))));
            break;
        case C_BTLEN:
            writeRef(st.args[1], ival((int32_t)toStr(evalExpr(st.args[0])).size()), st);
            break;
        case C_COVX: {
            Value src = evalExpr(st.args[0]);
            int32_t len = st.args[2] >= 0 ? toInt(evalExpr(st.args[2])) : 0;
            int32_t fmt = st.args[3] >= 0 ? toInt(evalExpr(st.args[3])) : 0;
            if (src.isStr) {
                std::string s = src.s;
                if (fmt == 1) { std::string t; for (size_t i = 0; i < s.size(); i++) if (s[i] != ',') t.push_back(s[i]); s = t; }
                writeRef(st.args[1], ival(strToInt(s, fmt == 2 ? 16 : 10)), st);
            } else writeRef(st.args[1], sval(formatInt(src.i, len, fmt)), st);
            break;
        }
        case C_SUBSTR: {
            std::string s = toStr(evalExpr(st.args[0]));
            int32_t start = st.args[2] >= 0 ? toInt(evalExpr(st.args[2])) : 0;
            int32_t len = st.args[3] >= 0 ? toInt(evalExpr(st.args[3])) : 0;
            std::string out;
            if (start >= 0 && (size_t)start < s.size() && len > 0) out = s.substr((size_t)start, (size_t)len);
            writeRef(st.args[1], sval(out), st);
            break;
        }
        case C_PLAY: {
            int32_t ch = toInt(evalExpr(st.args[0]));
            int32_t id = st.args.size() > 1 ? toInt(evalExpr(st.args[1])) : 0;
            int32_t loop = st.args.size() > 2 ? toInt(evalExpr(st.args[2])) : 0;
            host_.play(id, ch, loop);
            break;
        }
        default:
            host_.unknownCommand(st.text);
            break;
    }
}
