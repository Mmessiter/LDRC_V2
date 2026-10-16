// The transmitter's own command-line sums (ESP32-board2 board4/nextion-emulator/lib/LdrcCli), for dev/diff_test.js to
// hold the phone's Diff & execute page against: one case a line, "kind hex [hex]", the answer hex-coded on one line.
#include "LdrcCli.h"
#include <cstdio>
#include <iostream>
#include <string>
using namespace ldrc;
static std::string unhex(const std::string &h) { std::string s; for (size_t i = 0; i + 1 < h.size(); i += 2) s.push_back((char) strtol(h.substr(i, 2).c_str(), nullptr, 16)); return s; }
static std::string hex(const std::string &s) { std::string h; char b[3]; for (unsigned char c : s) { snprintf(b, sizeof b, "%02x", c); h += b; } return h; }
static std::string joined(const std::vector<std::string> &v) { std::string s; for (size_t i = 0; i < v.size(); ++i) { if (i) s += '\x1f'; s += v[i]; } return s; }
int main() {
    std::string kind, a, b;
    while (std::cin >> kind >> a) {
        if (kind == "key") std::cin >> b;
        const std::string x = unhex(a == "-" ? "" : a), y = unhex(b == "-" ? "" : b);
        std::vector<std::string> v;
        if (kind == "lines") { cliLines(x, v); std::cout << hex(joined(v)) << "\n"; }
        else if (kind == "cmds") { cliCommands(x, v); std::cout << hex(joined(v)) << "\n"; }
        else if (kind == "whole") { cliLines(x, v); std::cout << (cliDiffWhole(v) ? 1 : 0) << "\n"; }
        else if (kind == "key") std::cout << cliFileKey("/rfdiff/" + x, "/rfdiff/" + y) << "\n";
        else if (kind == "safe") std::cout << hex(cliModelPrefix(x)) << "\n";
        else if (kind == "err") std::cout << hex(cliErrorWords(x)) << "\n";
        else if (kind == "when") std::cout << hex(cliDiffWhen("/rfdiff/" + x)) << "\n";
        else std::cout << "?\n";
    }
    return 0;
}
