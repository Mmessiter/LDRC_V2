# TXV2 rev-A main board — single source of truth for nets.
# Derived from TXV2/HARDWARE.md (frozen 2026-07-06 + charging amendment
# approved 2026-07-19). Both generate_sch.py and generate_pcb.py import
# this file, so schematic and board can never disagree.

# ── Teensy 4.1 socket (edge pins 0-41 + GND/VIN/3V3/VBAT) ──────────
TEENSY = {
    "0":  "NEXTION_TX",     # Serial1 RX1 <- display
    "1":  "NEXTION_RX",     # Serial1 TX1 -> display
    "2":  "WS2812_DATA",
    "3":  "BUZZER",         # reserved / spare PWM
    "4":  "PWRBTN_SENSE",
    "5":  "LATCH_OFF",      # Pololu 2808 OFF
    "6":  "HANDSHAKE_A",    # moved from 24 (2026-07-19: 24=A10 freed for VBAT divider)
    "7":  "LINK_RX2",       # <- ESP32 TX
    "8":  "LINK_TX2",       # -> ESP32 RX
    "9":  "NRF_CE",
    "10": "NRF_CSN",
    "11": "SPI_MOSI",
    "12": "SPI_MISO",
    "13": "SPI_SCK",
    "14": "GIMBAL1",  "15": "GIMBAL2",  "16": "GIMBAL3",  "17": "GIMBAL4",
    "18": "I2C_SDA",  "19": "I2C_SCL",  # BQ25887 + Qwiic expansion
    "20": "KNOB5",    "21": "KNOB6",    "22": "KNOB7",    "23": "KNOB8",
    "24": "VBAT_SENSE",     # A10 — 47k/15k divider from VBAT_SW (INA219 dropped 2026-07-19)
    "25": "HANDSHAKE_B",    # Teensy->ESP attention
    "26": "SW1", "27": "SW2", "28": "SW3", "29": "SW4",
    "30": "SW5", "31": "SW6", "32": "SW7", "33": "SW8",
    "34": "TRIM1", "35": "TRIM2", "36": "TRIM3", "37": "TRIM4",
    "38": "TRIM5", "39": "TRIM6", "40": "TRIM7", "41": "TRIM8",
    "GND": "GND", "VIN": "+5V", "3V3": "+3V3_T", "VBAT": "RTC_VBAT",
}

# ── ESP32-S3 DevKitC-1U socket (net names by module GPIO) ──────────
ESP32 = {
    "17": "LINK_RX2_E",     # U1RXD <- Teensy TX2 (net joins LINK_TX2)
    "18": "LINK_TX2_E",     # U1TXD -> Teensy RX2 (net joins LINK_RX2)
    "8":  "HANDSHAKE_A",
    "9":  "HANDSHAKE_B",
    "5V": "+5V", "GND": "GND",
    # all remaining GPIOs -> labelled spare header
}
# NOTE: ESP32 GPIO17 connects to net LINK_TX2 and GPIO18 to LINK_RX2
# (crossover happens in the schematic, the _E names above are reminders).

# ── nRF24L01+PA+LNA socket (2x4) ───────────────────────────────────
NRF24 = {
    "1": "GND", "2": "+3V3_RF", "3": "NRF_CE", "4": "NRF_CSN",
    "5": "SPI_SCK", "6": "SPI_MOSI", "7": "SPI_MISO", "8": "NRF_IRQ_NC",
}

# ── Connectors (JST-XH unless stated) ──────────────────────────────
CONNECTORS = {
    "J_NEXTION":  ["GND", "NC", "+5V", "NEXTION_RX", "NEXTION_TX"],
    # 5-pin 0.1" male header, V1's EXACT VNEXTION order — DO NOT CHANGE
    # (Malcolm 2026-07-19): the display loom doubles as the FTDI-upload
    # lead. Housing: GND(black), skip(=FTDI CTS), 5V(red),
    # RX(yellow <- FTDI TXD, driven by Teensy TX1), TX(blue -> FTDI RXD).
    # FTDI's 6th pin (DTR) sits outside the housing (Malcolm bends it).
    # This is the ONE deliberate Dupont survivor among the XH fleet.
    "J_BAT":      ["VBAT_RAW", "GND"],                          # XT30
    "J_BAL":      ["CELL_MID"],                                 # XH-2: CELL_MID + GND (charger balance tap)
    "J_PWRBTN":   ["PWRBTN_SENSE", "LATCH_OFF_BTN", "GND"],     # XH-3 (button + latch loom, as V1 wiring)
    "J_GIMBal_L": ["+3V3_T", "GIMBAL1", "GIMBAL2", "GND"],      # XH-4 left gimbal (2 axes)
    "J_GIMBal_R": ["+3V3_T", "GIMBAL3", "GIMBAL4", "GND"],      # XH-4 right gimbal
    "J_KNOBS":    ["+3V3_T", "KNOB5", "KNOB6", "KNOB7", "KNOB8", "GND"],  # XH-6
    "J_SWITCHES": ["SW1","SW2","SW3","SW4","SW5","SW6","SW7","SW8","GND"], # XH-9
    "J_TRIMS":    ["TRIM1","TRIM2","TRIM3","TRIM4","TRIM5","TRIM6","TRIM7","TRIM8","GND"], # XH-9
    "J_WS2812":   ["+5V", "WS2812_DATA", "GND"],                # XH-3 panel LED
    # J_BUDDY / J_JRBAY: DROPPED 2026-07-19 — unused on V1, buddy is wireless now.
    "J_QWIIC":    ["GND", "+3V3_T", "I2C_SDA", "I2C_SCL"],      # JST-SH 1.0 Qwiic
    "J_I2C_XH":   ["GND", "+3V3_T", "I2C_SDA", "I2C_SCL"],      # XH-4 twin
    "J_ESP_SPARE": "all unused DevKitC pins -> labelled 2.54 header",
}

# ── Power chain (INA219 DROPPED 2026-07-19 — divider instead) ──────
# VBAT_RAW (XT30) -> Pololu 2808 latch (socket) -> VBAT_SW ->
#   buck module (socket) -> +5V -> Teensy VIN + DevKitC 5V.
# VBAT_SW -> 47k -> VBAT_SENSE (Teensy 24/A10) -> 15k -> GND + 100nF.
#   Post-latch: zero drain when off. Ratio 62/15 = 4.133.
#   (While CHARGING, pack + per-cell volts come from the BQ25887 ADC.)
# +3V3_T  = Teensy's onboard 3.3 V regulator output (sensor/pot rail).
# +3V3_RF = dedicated LDO from +5V for the nRF24 (AMS1117-3.3 + bulk).
# RTC_VBAT = CR2032 holder -> Teensy VBAT pin.

# ── Charger block (BQ25887, approved amendment; full values in
#    memory txv2-usbc-charger + Balancer 5 Click reference) ─────────
# USB-C 16P (charge-only): VBUS -> charger VBUS; CC1/CC2 5.1k pulldowns.
# BQ25887: BAT/SNS -> VBAT_RAW (pack side of INA219, so charge current
#   is NOT counted as consumption); MID -330R-> CELL_MID;
#   CBSET -2x68R(1206 parallel)-> CELL_MID; TS: REGN-5.11k-TS-7.5k-GND
#   (7.5k = no-NTC default; swap to 30k if pack NTC fitted);
#   ILIM 374R; PSEL,CD -> GND; SDA/SCL -> I2C bus via level note (bus
#   is 3.3 V, BQ25887 I2C is 3.3 V tolerant open-drain - OK, shared
#   pull-ups); STAT -> amber LED <- 470R <- VBUS; green PWR LED VBUS.
# L1 1uH IHLP-2020 PMID->SW; caps: VBUS 1uF, PMID 2x10uF/25V,
#   BAT 10uF+47pF, REGN 4.7uF, BTST 47nF.
# I2C address 0x6A (INA219 0x40 - no clash).
