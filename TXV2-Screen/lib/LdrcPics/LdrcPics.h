// The model pictures: the screen's own chooser (screen 1.5.0), and photos sent from a phone.
//
// The pictures live on the SCREEN's card only: /images/<name>.565 (the release's) and /images/mine/<name>.565 (the
// pilot's own, sent from a phone; never touched by an update, and found first). Each is 320 x 200 pixels, RGB565,
// little-endian, after a 4-byte header (u16 width, u16 height). The Teensy keeps only the NAME of each model's
// picture (8 characters, ModelImageFileName). On a Nextion the Teensy listed its own card's /Images/*.jpg, because a
// Nextion could not tell it what was on the screen's card: every picture had to be on both cards. Now, when the
// Teensy shows its "Choose image" page (ImageView), the screen covers it with this chooser, and on OK or Cancel
// answers "LDRCIMG <name>" (Cancel: "LDRCIMG" alone). The Teensy stores the name, saves the model and goes back to its
// options page, as its own OK button did (TXV1B include/ChooseImage.h, ChooseImageFromScreen, B21).
//
// "Add photo" shows a QR code: the phone opens http://<screen>/photo?k=<key> (hmi/web/photo.html on the card), the
// pilot fits a photo into the frame, and the PHONE makes it exactly 320 x 200 RGB565 before it sends it. The key is
// made afresh for each chooser and is good only while the chooser is open on the transmitter.
//
// Portable: no Arduino, tested on the Mac (hmi/test_pics). The drawing and the card are src/pics_device.h.
#pragma once
#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>

namespace ldrc {

static const int PIC_W = 320, PIC_H = 200;                          // the picture frame on every page that shows one
static const uint32_t PIC_FILE_BYTES = 4u + (uint32_t) PIC_W * PIC_H * 2u;
static const char PIC_NONE[] = "Noimage";                           // the Teensy's word for "no picture"
static const int PIC_NAME_MAX = 8;                                  // ModelImageFileName[9] on the Teensy
static const char LDRC_IMAGE_WORD_[] = "LDRCIMG";                   // (LdrcLink.h has it as LDRC_IMAGE_WORD)

bool picNameOk(const std::string &n);                              // 1..8 of A-Z a-z 0-9 _ -, and not "Noimage"
bool picSameName(const std::string &a, const std::string &b);       // FAT: case does not count
std::string picNameFromPath(const std::string &path);               // "sd0/images/Edge540.jpg" -> "Edge540"
std::string picNameSuggest(const std::string &model);              // from the model's name: "Goblin 700" -> "Goblin70"
bool picHeaderOk(const uint8_t *b, size_t n);                       // the first 4 bytes of a .565: 320 x 200

struct PicEntry { std::string name; bool mine = false; };          // name PIC_NONE: the "No picture" tile
// What the chooser offers: "No picture" first, then every name the Teensy can keep, the pilot's own before the release's
// of the same name (the list from the card comes sorted that way). picIndexOf: where a name is (0 if it is not there).
void picBuildList(const std::vector<PicEntry> &fromCard, std::vector<PicEntry> &out, int maxEntries = 240);
int picIndexOf(const std::vector<PicEntry> &list, const std::string &name);

// Where things are on the 800 x 480 panel.
struct PicRect {
    int x = 0, y = 0, w = 0, h = 0;
    PicRect() {}
    PicRect(int x_, int y_, int w_, int h_) : x(x_), y(y_), w(w_), h(h_) {}
    bool has(int px, int py, int slop = 0) const { return px >= x - slop && px < x + w + slop && py >= y - slop && py < y + h + slop; }
};
static const int PIC_COLS = 4, PIC_ROWS = 2, PIC_PER_PAGE = PIC_COLS * PIC_ROWS;
static const int PIC_THUMB_W = PIC_W / 2, PIC_THUMB_H = PIC_H / 2;
static const int PIC_STRIP_H = 58;                                  // the title strip along the top
PicRect picTile(int slot);                                          // a thumbnail and its border, slot 0..7
PicRect picLabel(int slot);                                         // the name under it
PicRect picButton(int i);                                           // the four buttons along the bottom, 0..3
PicRect picArrow(int dir);                                          // -1: the pages before, +1: after
PicRect picStatus();                                                // the line above the buttons
PicRect picQr();                                                    // "Add photo": the code's white square
PicRect picInfo();                                                  // "Add photo": the words beside it
PicRect picHelp();                                                  // "Help", in the title strip (where the Teensy's page has it)

struct PicsHost {
    virtual ~PicsHost() {}
    virtual uint32_t ms() = 0;
    virtual void list(std::vector<PicEntry> &out) = 0;              // every picture on the card whose name the Teensy can keep
    virtual bool removeMine(const std::string &name) = 0;           // one of the pilot's own photos
    virtual void answer(const std::string &name) = 0;               // "LDRCIMG <name>" to the Teensy ("" = keep what it has)
    virtual bool wifiUp() = 0;                                      // on a network now
    virtual int flying() = 0;                                       // why the radios must stay off (0: they may be on)
    virtual std::string address() = 0;                              // our address on that network
    virtual uint32_t random() = 0;
    virtual void wifiWanted(bool on) = 0;                           // the chooser needs the WiFi, whatever the pilot's switch says
    virtual void wifiSetup() = 0;                                   // the WiFi page
    virtual void keepAwake() = 0;                                   // the Teensy's screen saver and power-off timer: someone is here
    virtual void help() = 0;                                        // the Teensy's own help for this page (its Help button's script)
};

class Pictures {
public:
    enum Mode { CLOSED, CHOOSE, ASK_DELETE, RECEIVE, ANSWERED };
    enum Press { P_NONE = 0, P_BUTTON = 1, P_TILE = 10, P_BACK = 20, P_ON = 21, P_HELP = 30 };   // P_BUTTON + i, P_TILE + slot
    static const uint32_t RESEND_MS = 700, GIVE_UP_MS = 4000, RECEIVE_IDLE_MS = 600000, AWAKE_EVERY_MS = 20000, AWAKE_FOR_MS = 180000;
    static const int MAX_ENTRIES = 240;

    explicit Pictures(PicsHost &h) : host_(h) {}

    // The Teensy's page.
    void open(const std::string &model, const std::string &current);   // it has shown ImageView
    void setModel(const std::string &model);                        // its t0 text (arrives just after the page)
    void setCurrent(const std::string &name);                       // its exp0 path: the model's picture now
    void pageGone();                                                // it has left the page: close
    bool gaveUp() { bool g = gaveUp_; gaveUp_ = false; return g; }   // the Teensy did not answer (firmware before B21)

    // The finger (debounced by the caller): down, then up where it was lifted.
    void touchDown(int x, int y);
    void touchUp(int x, int y);
    void poll();

    // The phone.
    bool keyOk(const std::string &k) const;                         // an upload or the page: only while the chooser is open
    bool acceptsUpload() const { return mode_ == CHOOSE || mode_ == RECEIVE; }
    const std::string &key() const { return key_; }
    std::string url() const;                                        // http://<address>/photo?k=<key>
    std::string shortUrl() const;                                   // <address>/photo?k=<key> (what a person types)
    void uploadBegun(const std::string &name);
    void uploadBytes(uint32_t n);
    void uploadEnded(bool ok, const std::string &name, const std::string &why);

    // What to draw.
    Mode mode() const { return mode_; }
    int page() const { return page_; }
    int pages() const { return list_.empty() ? 1 : (int) ((list_.size() + PIC_PER_PAGE - 1) / PIC_PER_PAGE); }
    int selected() const { return sel_; }
    const std::vector<PicEntry> &entries() const { return list_; }
    int entryAt(int slot) const;                                    // the entry in that slot of this page, or -1
    const std::string &model() const { return model_; }
    std::string title() const;
    const std::string &status() const { return status_; }
    int statusTone() const { return tone_; }                        // 0 plain, 1 good, -1 bad
    int pressed() const { return pressed_; }
    std::string buttonText(int i) const;                            // "" = no button there
    bool buttonOn(int i) const;
    bool arrowShown(int dir) const;
    bool helpShown() const { return mode_ == CHOOSE; }
    uint32_t layout() const { return layout_; }                     // changes when everything must be drawn afresh

private:
    PicsHost &host_;
    Mode mode_ = CLOSED;
    std::vector<PicEntry> list_;
    std::string model_, current_, status_, key_, answer_, uploadName_, error_;
    int tone_ = 0, page_ = 0, sel_ = 0, pressed_ = 0, upPercent_ = -1;
    bool touched_ = false, gaveUp_ = false, wifiAsked_ = false;
    uint32_t answeredAt_ = 0, sentAt_ = 0, receiveAt_ = 0, touchAt_ = 0, awakeAt_ = 0, layout_ = 1;

    void reload();
    void select(int i);
    void selectName(const std::string &name, bool mine);
    void say(const std::string &s, int tone) { status_ = s; tone_ = tone; }
    void answer(const std::string &name);
    void enterReceive();
    void receiveStatus();
    void wifi(bool on) { if (wifiAsked_ != on) { wifiAsked_ = on; host_.wifiWanted(on); } }
    int at(int x, int y) const;
    void act(int what);
};

}  // namespace ldrc
