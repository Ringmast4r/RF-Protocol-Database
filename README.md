# RF Protocol Database

**The largest open-source unified Sub-GHz RF device protocol database.**

425 device signatures across 40 categories, merged from 4 authoritative sources. Covers the 300-928 MHz ISM spectrum -- every garage door opener, weather station, car key fob, TPMS sensor, security alarm, smart meter, and IoT device that transmits below WiFi frequencies.

## Stats

| Metric | Count |
|--------|-------|
| **Total Protocols** | 425 |
| **Categories** | 40 |
| **Sources** | 4 |
| **Modulation Types** | OOK, FSK, ASK, Manchester, DMC |
| **Frequency Bands** | 315, 345, 433, 868, 915 MHz ISM |

## Files

| File | Format | Description |
|------|--------|-------------|
| `rf_protocols.json` | JSON | Full database with all fields |
| `rf_protocols.csv` | CSV | Flat export for spreadsheets and SQL import |
| `build.py` | Python | Build script to regenerate from upstream sources |

## Categories

| Category | Count |
|----------|-------|
| Other Sensors & Devices | 89 |
| Temperature & Humidity Sensors | 72 |
| Weather Stations & Sensors | 51 |
| TPMS (Tire Pressure) | 28 |
| Energy & Water Meters | 26 |
| Smoke & Security Alarms | 22 |
| Gate & Garage Remotes | 19 |
| Automotive Key Fobs | 16 |
| Remote/Keyfob | 11 |
| Home Automation & Blinds | 5 |
| Ceiling Fans | 5 |
| BBQ & Kitchen Thermometers | 4 |
| Doorbells | 2 |
| Rolling Code Systems | 2 |
| Restaurant Pagers | 2 |
| + 25 more categories | ... |

## Sources

| Source | Protocols | Description |
|--------|-----------|-------------|
| **URH-NG** | 356 | Pre-merged database from rtl_433, Flipper-ARF, and ProtoPirate automotive decoders |
| **Zero-Sploit FlipperZero-Subghz-DB** | 52 | Unique protocol/frequency combinations extracted from 13,716 real-world .sub captures |
| **RTL_433 (latest source)** | 14 | Newer device decoders not yet in URH-NG |
| **RTL_433 (JSON export)** | 3 | Edge cases from original GigLez import |

## JSON Schema

```json
{
  "version": "2.0.0",
  "total_devices": 425,
  "sources": { "urh_ng": 356, "zero_sploit": 52, "rtl433_src": 14 },
  "categories": { "Weather Stations & Sensors": 51, "TPMS (Tire Pressure)": 28, ... },
  "devices": [
    {
      "device_id": "urh_acurite_592txr_temp_humidity",
      "name": "Acurite 592TXR temp/humidity, 5n1, Atlas weather station",
      "modulation": "PWM",
      "encoding": null,
      "bits": "88",
      "checksum": "add_bytes,crc16lsb,crc8le",
      "category": "Weather Stations & Sensors",
      "manufacturer": "Acurite",
      "source": "urh_ng",
      "frequency": null,
      "short_width": null,
      "long_width": null
    }
  ]
}
```

## CSV Schema

```
name,category,manufacturer,modulation,encoding,frequency,short_width,long_width,bits,checksum,source,device_id
```

## Usage

### Python
```python
import json

with open('rf_protocols.json') as f:
    db = json.load(f)

# Search by category
weather = [d for d in db['devices'] if 'Weather' in d.get('category', '')]
print(f"{len(weather)} weather protocols")

# Search by manufacturer
acurite = [d for d in db['devices'] if d.get('manufacturer') == 'Acurite']
print(f"{len(acurite)} Acurite devices")

# Search by modulation
ook = [d for d in db['devices'] if d.get('modulation') == 'OOK']
print(f"{len(ook)} OOK-modulated devices")
```

### JavaScript
```javascript
const db = await fetch('rf_protocols.json').then(r => r.json());

// Filter by frequency band
const ism433 = db.devices.filter(d => d.frequency && d.frequency > 433e6 && d.frequency < 434e6);
```

### SQL Import
```sql
CREATE TABLE rf_protocols (
    name TEXT, category TEXT, manufacturer TEXT,
    modulation TEXT, encoding TEXT, frequency BIGINT,
    short_width INT, long_width INT, bits TEXT,
    checksum TEXT, source TEXT, device_id TEXT
);

\copy rf_protocols FROM 'rf_protocols.csv' CSV HEADER;
```

## Rebuilding

To regenerate the database from upstream sources:

```bash
# Clone upstream repos into sibling directories
git clone https://github.com/merbanan/rtl_433.git
git clone https://github.com/PentHertz/urh-ng.git
git clone https://github.com/Zero-Sploit/FlipperZero-Subghz-DB.git

# Run build script
python3 build.py
```

## Upstream Sources

- [rtl_433](https://github.com/merbanan/rtl_433) -- GPL-2.0 -- Generic data receiver for ISM band devices
- [URH-NG](https://github.com/PentHertz/urh-ng) -- GPL-3.0 -- Universal Radio Hacker Next Generation
- [FlipperZero-Subghz-DB](https://github.com/Zero-Sploit/FlipperZero-Subghz-DB) -- 13,716 real-world .sub captures
- [Flipper-ARF](https://github.com/D4C1-Labs/Flipper-ARF) -- GPL-3.0 -- Automotive Research Firmware
- [ProtoPirate](https://github.com/RocketGod-git/ProtoPirate) -- GPL-3.0 -- Rolling code analysis

## Used By

- [WiFi Mothership](https://wifimothership.com/pages/rf-spectrum.html) -- RF Spectrum Analyzer page

## License

Database compilation: MIT. Individual protocol definitions retain their upstream licenses (GPL-2.0 for rtl_433, GPL-3.0 for URH-NG/Flipper-ARF/ProtoPirate).

---

A [Net // Works](https://networks.com) product.
