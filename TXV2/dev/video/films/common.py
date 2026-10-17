"""Pictures several films share (17 Oct 2026): the front page as every film shows it - RAW 420 MCM (3), Bank 1, Rate 1."""
from filmkit import prefix
FRONT_CONNECTED = prefix('13.txt', '13_conn', [
    ('bt0.txt="Motor is ON"\nbt0.bco=2016\nbt0.bco2=2016\nbt0.pco=0\nbt0.pco2=0', 'bt0.txt="Motor is OFF"\nbt0.bco=63488\nbt0.bco2=63488\nbt0.pco=65535\nbt0.pco2=65535'),
    ('RPM: 2150', 'RPM: 0'), ('Amps: 12.4', 'Amps: 0.3'), ('mAh: 345', 'mAh: 0'), ('ESC: 52.3', 'ESC: 21.5')])
# no model switched on: the same model loaded, the same owner and clock as the connected page
FRONT_NO_MODEL = prefix('13.txt', '13_nomodel') + ('ModelName.txt="RAW 420 MCM (3)"\nexp0.path="sd0/images/Bthundr1.jpg"\nvis exp0,1\nOwner.txt="Malcolm Messiter"\n'
                                                   'ams.txt="AMS is on"\nt4.txt="Bank 1"\nvis rate,1\nrate.txt="Rate 1"\nDateTime.txt="10 October 2026 17:14:07"\n')
MODEL_PICTURE = 'sd0/images/Bthundr1.jpg'                             # (RAW 420 MCM's picture on the front page: Malcolm's own)
