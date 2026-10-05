// NextionScript — a small interpreter for the Nextion HMI event-code subset used by
// TX_NEXTION.HMI (LDRC transmitter V1).  Portable C++11: no exceptions, no RTTI,
// only <string>/<vector>; compiles for ESP32 Arduino and for host clang++ (tests in
// hmi/test_script/).
//
// Language notes (Nextion Instruction Set, as the real hardware behaves):
//  * One statement per line.  `//` comments anywhere (outside quotes).
//  * Assignment  ref=expr  ref+=expr  -= *= /= %= &= |= ^= <<= >>=  ref++  ref--
//    ref is  comp.attr | page.comp.attr | p[expr].b[expr].attr | sysvar
//    `txt` is a string attribute; every other attribute is an int32 slot.
//    `+=` on txt concatenates; ints coerce to decimal text when mixed with a string.
//  * Expressions are evaluated LEFT TO RIGHT WITH NO OPERATOR PRECEDENCE, exactly
//    like the Nextion: 1+2*3 is 9, not 7.  Parentheses group.  Shifts by >=32 give 0
//    (ARM behaviour, so `30<<88` is 0).  Division/modulo by zero gives 0.
//  * if(cond) / while(cond) / for(init;cond;step) each need `{` on the next line
//    (or trailing on the same line); `}` closes; `}else`, `}else if(cond)`, and a
//    bare `else` line are all accepted.  cond: comparisons ==,!=,<,>,<=,>= joined by
//    && / || (&& binds tighter), parentheses allowed, strings compare with ==/!=.
//  * Commands: print, prints, printh, click, vis, page, btlen/strlen, covx, substr,
//    play.  `delay=ms` calls delayMs.  Any other one-word assignment (dim=, bkcmd=,
//    sys0=, …) goes to setSys(); if that returns false the raw line goes to
//    unknownCommand().  Every other verb (sendme, ref, cle, tsw, cov, doevents …)
//    parses without error and is routed to unknownCommand(line) at run time.
//  * Colour names: WHITE BLACK RED GREEN BLUE GRAY YELLOW BROWN.
//  * `page X` does not change the page the running snippet resolves bare refs
//    against; the host decides what to run next (postinitialize etc.).
//
// Execution is a flat statement list with pre-resolved jumps: no recursion per
// statement, so it is safe on an 8 KB ESP32 task stack.  The only recursion is
// parenthesis nesting in expressions/conditions, capped at a small depth.

#ifndef NEXTION_SCRIPT_H
#define NEXTION_SCRIPT_H

#include <stdint.h>
#include <stddef.h>
#include <string>
#include <vector>

class NextionHost {
public:
    virtual ~NextionHost() {}
    // Component attributes.  attr is never "txt" here (txt goes through getTxt/setTxt).
    virtual int32_t getInt(const std::string& page, const std::string& comp, const std::string& attr) = 0;
    virtual void setInt(const std::string& page, const std::string& comp, const std::string& attr, int32_t v) = 0;
    virtual std::string getTxt(const std::string& page, const std::string& comp) = 0;
    virtual void setTxt(const std::string& page, const std::string& comp, const std::string& s) = 0;
    // Raw bytes for the serial link (print / prints / printh).
    virtual void send(const uint8_t* data, size_t len) = 0;
    // click comp,1 → press=true ; click comp,0 → press=false
    virtual void click(const std::string& page, const std::string& comp, bool press) { (void)page; (void)comp; (void)press; }
    virtual void vis(const std::string& page, const std::string& comp, bool on) { (void)page; (void)comp; (void)on; }
    virtual void gotoPage(const std::string& name) { (void)name; }
    virtual void delayMs(uint32_t ms) { (void)ms; }
    // play ch,id,loop  (Nextion audio component syntax)
    virtual void play(int id, int channel, int loop) { (void)id; (void)channel; (void)loop; }
    virtual void unknownCommand(const std::string& line) { (void)line; }
    // System / global variables (dim, bauds, bkcmd, sys0, user globals from Program.s …).
    // setSys returns false when it does not handle the name; the raw line then goes to unknownCommand.
    virtual int32_t getSys(const std::string& name) { (void)name; return 0; }
    virtual bool setSys(const std::string& name, int32_t v) { (void)name; (void)v; return false; }
    // Needed for p[id].b[id].attr and `page <number>`.  Defaults: decimal id / "b<id>".
    virtual std::string pageNameById(int32_t id);
    virtual std::string compNameById(const std::string& page, int32_t id);
};

class NextionScript {
public:
    NextionScript(NextionHost& host, const std::string& currentPage);

    // Parse only.  false → lastError() / lastErrorLine() describe the first bad line.
    bool compile(const std::string& code);
    // compile + execute.  false on a parse error, or when execution was cut short
    // (runaway loop guard); lastError() explains.  selfComp names the component whose
    // event this is (used only in error messages).
    bool run(const std::string& code, const std::string& selfComp = std::string());
    // Execute the last successfully compiled program again.
    bool runCompiled(const std::string& selfComp = std::string());

    const std::string& lastError() const { return err_; }
    int lastErrorLine() const { return errLine_; }        // 1-based, 0 = none
    const std::string& page() const { return page_; }
    void setPage(const std::string& p) { page_ = p; }
    void setMaxSteps(uint32_t n) { maxSteps_ = n; }       // runaway-loop guard (default 200000)
    size_t statementCount() const { return stmts_.size(); }

    // ---- internal representation (public only so the .cpp helpers can use it) ----
    struct Tok { uint8_t t; uint8_t op; int32_t i; int ref; std::string s; };
    typedef std::vector<Tok> Expr;
    struct Ref { uint8_t kind; std::string page; int pageExpr; std::string comp; int compExpr; std::string attr; };
    struct Cond { uint8_t kind; uint8_t cmp; int l; int r; std::vector<int> kids; };
    struct Stmt {
        uint8_t kind; uint8_t op; uint8_t cmd;
        int ref; int expr; int jump; int line;
        std::vector<int> args;   // per-command operand indices (expr or ref)
        std::string text;        // raw line (unknown cmd / sys assignment), page name, printh bytes
    };
    struct Value { bool isStr; int32_t i; std::string s; };
    struct Block {               // compile-time block-stack entry
        uint8_t kind; int openIdx; bool awaitingBrace; bool hasStep; Stmt step; std::vector<int> pendingElse;
    };

private:
    bool fail(int line, const std::string& msg);
    bool parseLine(const std::string& raw, int lineNo, std::vector<Block>& stack);
    bool parseOpener(const std::string& body, int lineNo, std::vector<Block>& stack);
    bool parseAssign(const std::string& s, int lineNo, Stmt& st, bool& isAssign);
    bool parseCommand(const std::string& s, int lineNo, Stmt& st);
    bool parseExpr(const std::string& s, int lineNo, int& idx);
    bool parseCond(const std::string& s, int lineNo, int& idx, int depth);
    bool parseRef(const std::string& s, size_t& pos, bool needAttr, int lineNo, int& idx);
    bool parseRefOnly(const std::string& s, bool needAttr, int lineNo, int& idx);

    bool execute();
    Value evalExpr(int idx);
    Value evalTokens(const Expr& e, size_t& pos, int depth);
    bool evalCond(int idx, int depth);
    Value readRef(int idx);
    void writeRef(int idx, const Value& v, const Stmt& st);
    bool resolveRef(int idx, std::string& page, std::string& comp, std::string& attr, bool& isSys);
    void doAssign(const Stmt& st);
    void doCommand(const Stmt& st);

    NextionHost& host_;
    std::string page_;
    std::string self_;
    std::string err_;
    int errLine_;
    uint32_t maxSteps_;
    std::vector<Stmt> stmts_;
    std::vector<Expr> exprs_;
    std::vector<Ref> refs_;
    std::vector<Cond> conds_;
    bool lastChainValid_;    // a bare `else` line may re-open the block closed just before
    Block lastChain_;
};

#endif
