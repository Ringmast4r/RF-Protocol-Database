"""Build unified RF protocol database from multiple sources.
Sources:
  1. RTL_433 JSON (existing GigLez export)
  2. RTL_433 latest C source files
  3. URH-NG SUPPORTED_PROTOCOLS.md (327 protocols)
  4. Zero-Sploit FlipperZero-Subghz-DB (13,716 .sub files)
  5. DarkFlippers Unleashed firmware (56 SubGHz protocols)
  6. UberGuidoZ Flipper Sub-GHz collection
  7. RocketGod Flipper_Zero SD dump
"""
import json, os, re, glob, csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GITHUBS = os.path.expanduser('~/Desktop/GITHUBS')
OTHER = os.path.join(GITHUBS, 'OTHER PEOPLES GITHUBS RSS')
OUTPUT = os.path.join(SCRIPT_DIR, 'rf_protocols.json')
OUTPUT_CSV = os.path.join(SCRIPT_DIR, 'rf_protocols.csv')
WM_OUTPUT = os.path.expanduser('~/Desktop/Websites/WiFiMothership.com/assets/data/rf_protocols_unified.json')


def load_rtl433_json():
    for path in [
        os.path.expanduser('~/Desktop/Websites/WiFiMothership.com/assets/data/rtl433_protocols.json'),
        os.path.join(GITHUBS, 'giglez', 'data', 'rtl_433_protocols.json'),
    ]:
        if os.path.isfile(path):
            with open(path) as f:
                return json.load(f).get('devices', [])
    return []


def parse_rtl433_sources():
    devices = []
    for src_dir in [os.path.join(OTHER, 'rtl_433', 'src', 'devices')]:
        if not os.path.isdir(src_dir):
            continue
        for cfile in sorted(glob.glob(os.path.join(src_dir, '*.c'))):
            if 'new_template' in cfile:
                continue
            basename = os.path.splitext(os.path.basename(cfile))[0]
            with open(cfile, encoding='utf-8', errors='ignore') as f:
                content = f.read()
            for m in re.finditer(r'r_device\s+const\s+(\w+)\s*=\s*\{', content):
                var_name = m.group(1)
                block = content[m.start():m.start()+2000]
                name_m = re.search(r'\.name\s*=\s*"([^"]+)"', block)
                name = name_m.group(1) if name_m else var_name
                mod = 'FSK' if 'FSK_PULSE' in block else 'OOK'
                short_m = re.search(r'\.short_width\s*=\s*(\d+)', block)
                long_m = re.search(r'\.long_width\s*=\s*(\d+)', block)
                devices.append({
                    'device_id': var_name, 'name': name, 'modulation': mod,
                    'short_width': int(short_m.group(1)) if short_m else None,
                    'long_width': int(long_m.group(1)) if long_m else None,
                    'category': categorize_device(name),
                    'manufacturer': extract_manufacturer(name),
                    'source': 'rtl433_src', 'source_file': basename + '.c',
                })
        break
    return devices


def parse_urh_ng():
    devices = []
    for path in [os.path.join(OTHER, 'urh-ng', 'SUPPORTED_PROTOCOLS.md')]:
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            content = f.read()
        current_category = 'Unknown'
        for line in content.split('\n'):
            cat_match = re.match(r'^## (.+?) \((\d+)\)', line)
            if cat_match:
                current_category = cat_match.group(1)
                continue
            if line.startswith('| ') and not line.startswith('| Protocol') and not line.startswith('|---'):
                parts = [p.strip() for p in line.split('|')[1:-1]]
                if len(parts) >= 3:
                    name, modulation = parts[0], parts[1]
                    bits = parts[2] if len(parts) > 2 else ''
                    checksum = parts[3] if len(parts) > 3 else ''
                    devices.append({
                        'device_id': f"urh_{re.sub(r'[^a-z0-9]', '_', name.lower())[:50]}",
                        'name': name,
                        'modulation': modulation.split('/')[0] if '/' in modulation else modulation,
                        'encoding': modulation.split('/')[1] if '/' in modulation else None,
                        'bits': bits if bits and bits != '—' else None,
                        'checksum': checksum if checksum and checksum != '—' else None,
                        'category': current_category,
                        'manufacturer': extract_manufacturer(name),
                        'source': 'urh_ng',
                    })
        break
    return devices


def parse_unleashed():
    devices = []
    proto_dir = os.path.join(OTHER, 'unleashed-firmware', 'lib', 'subghz', 'protocols')
    if not os.path.isdir(proto_dir):
        return devices
    skip = {'base', 'bin_raw', 'raw', 'protocol_items', 'keeloq_common', 'aes_common'}
    for cfile in sorted(glob.glob(os.path.join(proto_dir, '*.c'))):
        basename = os.path.splitext(os.path.basename(cfile))[0]
        if basename in skip:
            continue
        with open(cfile, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        name = basename.replace('_', ' ').title()
        for m in re.finditer(r'manufacture_name\s*=\s*"([^"]+)"', content):
            if m.group(1) and m.group(1) not in ('Unknown', ''):
                name = m.group(1)
                break
        mod = 'FSK' if any(x in content for x in ['2FSK', 'GFSK', 'MSK']) else 'OOK'
        te_s = re.search(r'te_short\s*=\s*(\d+)', content)
        te_l = re.search(r'te_long\s*=\s*(\d+)', content)
        devices.append({
            'device_id': f"unleashed_{basename}", 'name': name, 'modulation': mod,
            'short_width': int(te_s.group(1)) if te_s else None,
            'long_width': int(te_l.group(1)) if te_l else None,
            'category': categorize_flipper_protocol(basename),
            'manufacturer': extract_manufacturer(name),
            'source': 'unleashed_firmware', 'source_file': basename + '.c',
        })
    return devices


def parse_sub_files(base_dir, source_name):
    devices = []
    if not os.path.isdir(base_dir):
        return devices
    combos = {}
    for root, _, files in os.walk(base_dir):
        for fname in files:
            if not fname.endswith('.sub'):
                continue
            rel = os.path.relpath(root, base_dir).replace('\\', '/').split('/')
            cat = rel[0].replace('_', ' ').replace('-', ' ').strip() if rel[0] != '.' else 'Uncategorized'
            try:
                with open(os.path.join(root, fname), encoding='utf-8', errors='ignore') as f:
                    header = f.read(2000)
                freq, preset, protocol = None, None, None
                for line in header.split('\n'):
                    if line.startswith('Frequency:'): freq = int(line.split(':')[1].strip())
                    elif line.startswith('Preset:'): preset = line.split(':')[1].strip()
                    elif line.startswith('Protocol:'): protocol = line.split(':')[1].strip()
                if freq and protocol and protocol != 'RAW':
                    key = f"{protocol}_{freq}_{cat}"
                    if key not in combos:
                        combos[key] = {'protocol': protocol, 'frequency': freq, 'preset': preset, 'category': cat, 'count': 0}
                    combos[key]['count'] += 1
            except:
                continue
    for key, info in combos.items():
        mod = 'FSK' if info['preset'] and any(x in info['preset'] for x in ['2FSK', 'GFSK', 'MSK']) else 'OOK'
        devices.append({
            'device_id': f"{source_name}_{info['protocol'].lower().replace(' ','_')}_{info['frequency']}",
            'name': f"{info['protocol']} ({info['category']})",
            'modulation': mod, 'frequency': info['frequency'],
            'category': info['category'], 'manufacturer': info['protocol'],
            'source': source_name, 'sample_count': info['count'],
        })
    return devices


def parse_wmbusmeters():
    """Parse wmbusmeters C++ driver files for wireless meter protocols."""
    devices = []
    src_dir = os.path.join(OTHER, 'wmbusmeters', 'src')
    if not os.path.isdir(src_dir):
        return devices
    for cfile in sorted(glob.glob(os.path.join(src_dir, 'driver_*.cc'))):
        basename = os.path.splitext(os.path.basename(cfile))[0].replace('driver_', '')
        with open(cfile, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # Extract meter name from the driver registration
        name_m = re.search(r'"([^"]+)".*MeterType', content)
        if not name_m:
            name_m = re.search(r'addDriver\(\s*"([^"]+)"', content)
        name = name_m.group(1) if name_m else basename.replace('_', ' ').title()
        # Detect meter type
        meter_type = 'Utility Meter'
        n = (name + ' ' + content[:500]).lower()
        if 'water' in n: meter_type = 'Water Meter'
        elif 'heat' in n or 'thermal' in n: meter_type = 'Heat Meter'
        elif 'gas' in n: meter_type = 'Gas Meter'
        elif 'electric' in n or 'power' in n: meter_type = 'Electric Meter'
        elif 'smoke' in n: meter_type = 'Smoke Detector'
        # Extract manufacturer from content
        mfr = None
        mfr_m = re.search(r'[Mm]anufacturer.*?["\']([A-Z][a-z]+)', content)
        if mfr_m:
            mfr = mfr_m.group(1)
        devices.append({
            'device_id': f"wmbus_{basename}",
            'name': name,
            'modulation': 'FSK',  # Wireless M-Bus uses FSK
            'frequency': 868950000,  # 868.95 MHz standard
            'category': meter_type,
            'manufacturer': mfr or extract_manufacturer(name),
            'source': 'wmbusmeters',
            'source_file': os.path.basename(cfile),
        })
    return devices


def parse_lillygo_sub():
    """Parse ValeTheCyborg Lillygo Sub-GHz signal collection."""
    return parse_sub_files(os.path.join(OTHER, 'Lillygo-SubGhz-Signal'), 'lillygo_collection')


def parse_rogumaster():
    """Parse RogueMaster firmware for unique protocol decoders."""
    devices = []
    proto_dir = os.path.join(OTHER, 'flipperzero-firmware-wPlugins', 'lib', 'subghz', 'protocols')
    if not os.path.isdir(proto_dir):
        return devices
    # Only extract protocols NOT already in Unleashed
    unleashed_dir = os.path.join(OTHER, 'unleashed-firmware', 'lib', 'subghz', 'protocols')
    unleashed_names = set()
    if os.path.isdir(unleashed_dir):
        unleashed_names = {os.path.splitext(f)[0] for f in os.listdir(unleashed_dir) if f.endswith('.c')}
    skip = {'base', 'bin_raw', 'raw', 'protocol_items', 'keeloq_common', 'aes_common'}
    for cfile in sorted(glob.glob(os.path.join(proto_dir, '*.c'))):
        basename = os.path.splitext(os.path.basename(cfile))[0]
        if basename in skip or basename in unleashed_names:
            continue
        with open(cfile, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        name = basename.replace('_', ' ').title()
        for m in re.finditer(r'manufacture_name\s*=\s*"([^"]+)"', content):
            if m.group(1) and m.group(1) not in ('Unknown', ''):
                name = m.group(1)
                break
        mod = 'FSK' if any(x in content for x in ['2FSK', 'GFSK', 'MSK']) else 'OOK'
        te_s = re.search(r'te_short\s*=\s*(\d+)', content)
        te_l = re.search(r'te_long\s*=\s*(\d+)', content)
        devices.append({
            'device_id': f"roguemaster_{basename}", 'name': name, 'modulation': mod,
            'short_width': int(te_s.group(1)) if te_s else None,
            'long_width': int(te_l.group(1)) if te_l else None,
            'category': categorize_flipper_protocol(basename),
            'manufacturer': extract_manufacturer(name),
            'source': 'roguemaster_firmware', 'source_file': basename + '.c',
        })
    return devices


def parse_keyfob_db():
    """Parse gusgorman402/keyfobDB automotive CSV."""
    devices = []
    for csvfile in glob.glob(os.path.join(OTHER, 'keyfobDB', '*.csv')):
        try:
            with open(csvfile, encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                seen = set()
                for row in reader:
                    fcc_id = row.get('FCC_ID', row.get('fcc_id', ''))
                    freq = row.get('Frequency', row.get('frequency', ''))
                    make = row.get('Make', row.get('make', ''))
                    model = row.get('Model', row.get('model', ''))
                    year = row.get('Year', row.get('year', ''))
                    if not freq or not make:
                        continue
                    key = f"{make}_{freq}"
                    if key in seen:
                        continue
                    seen.add(key)
                    # Parse frequency to Hz
                    freq_hz = None
                    try:
                        freq_val = float(re.sub(r'[^\d.]', '', freq))
                        if freq_val < 1000:  # MHz
                            freq_hz = int(freq_val * 1e6)
                        else:
                            freq_hz = int(freq_val)
                    except:
                        pass
                    devices.append({
                        'device_id': f"keyfob_{make.lower().replace(' ','_')}_{freq}",
                        'name': f"{make} Key Fob ({freq} MHz)",
                        'modulation': 'OOK',
                        'frequency': freq_hz,
                        'category': 'Automotive Key Fob',
                        'manufacturer': make,
                        'source': 'keyfob_db',
                        'fcc_id': fcc_id,
                    })
        except:
            continue
    return devices


def parse_rc_switch():
    """Parse sui77/rc-switch protocol timing tables."""
    devices = []
    # rc-switch defines protocols in RCSwitch.cpp with timing arrays
    for srcfile in [os.path.join(OTHER, 'rc-switch', 'RCSwitch.cpp'), os.path.join(OTHER, 'rc-switch', 'src', 'RCSwitch.cpp')]:
        if not os.path.isfile(srcfile):
            continue
        with open(srcfile, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # Extract Protocol struct entries
        for i, m in enumerate(re.finditer(r'\{\s*(\d+)\s*,\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}\s*,\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}\s*,\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}', content)):
            pulse_len = int(m.group(1))
            devices.append({
                'device_id': f"rcswitch_proto_{i+1}",
                'name': f"RC-Switch Protocol {i+1}",
                'modulation': 'OOK',
                'short_width': pulse_len,
                'long_width': pulse_len * 3,  # Typical OOK ratio
                'category': 'Remote Control',
                'manufacturer': None,
                'source': 'rc_switch',
            })
        break
    return devices


def categorize_device(name):
    n = name.lower()
    if any(w in n for w in ['weather', 'rain', 'wind', 'barometer']): return 'Weather Station'
    if any(w in n for w in ['temperature', 'humidity', 'thermo', 'hygro', 'soil', 'pool']): return 'Temperature Sensor'
    if any(w in n for w in ['tpms', 'tire', 'tyre']): return 'TPMS'
    if any(w in n for w in ['garage', 'gate', 'came', 'nice', 'somfy', 'hormann', 'liftmaster', 'chamberlain']): return 'Gate/Garage'
    if any(w in n for w in ['doorbell', 'bell']): return 'Doorbell'
    if any(w in n for w in ['smoke', 'alarm', 'security', 'sensor', 'motion', 'window', 'door']): return 'Security/Alarm'
    if any(w in n for w in ['car key', 'key fob', 'keyfob', 'remote']): return 'Remote/Keyfob'
    if any(w in n for w in ['meter', 'ert', 'scm', 'water', 'gas', 'electric']): return 'Utility Meter'
    if any(w in n for w in ['bbq', 'meat', 'grill', 'kitchen']): return 'BBQ Thermometer'
    if any(w in n for w in ['blind', 'shade', 'curtain', 'automation']): return 'Home Automation'
    return 'Other'


def categorize_flipper_protocol(basename):
    n = basename.lower()
    gates = ['came', 'nice_flo', 'nice_flor', 'faac', 'hormann', 'gate_tx', 'secplus', 'megacode',
             'linear', 'chamberlain', 'kinggates', 'alutech', 'beninca', 'ditec', 'roger', 'mastercode',
             'nero', 'ido', 'marantec']
    remotes = ['princeton', 'holtek', 'smc5326', 'ansonic', 'bett', 'doitrand', 'clemsa', 'dickert',
               'phoenix', 'intertechno', 'elplast', 'power_smart', 'revers_rb2', 'feron', 'gangqi', 'hay21']
    blinds = ['somfy', 'dooya', 'jarolift', 'legrand']
    security = ['honeywell', 'magellan', 'hollarm', 'keyfinder']
    for g in gates:
        if g in n: return 'Gate/Garage Remote'
    for r in remotes:
        if r in n: return 'Remote Control'
    for b in blinds:
        if b in n: return 'Blinds/Shutters'
    for s in security:
        if s in n: return 'Security Sensor'
    if 'keeloq' in n: return 'Rolling Code (KeeLoq)'
    if 'treadmill' in n or 'nord_ice' in n: return 'Fitness Equipment'
    return 'Other'


def extract_manufacturer(name):
    known = ['Acurite', 'Oregon Scientific', 'LaCrosse', 'Fine Offset', 'Ambient Weather',
             'Bresser', 'ThermoPro', 'TFA', 'Honeywell', 'Schrader', 'Toyota', 'BMW',
             'Ford', 'Kia', 'Hyundai', 'Renault', 'Porsche', 'Subaru', 'Suzuki',
             'Chamberlain', 'LiftMaster', 'CAME', 'NICE', 'Somfy', 'Hormann',
             'Samsung', 'Philips', 'Nexus', 'Auriol', 'Eurochron', 'Rubicson',
             'Baldr', 'Inkbird', 'Kedsum', 'Danfoss', 'Watts', 'Vevor', 'Emos',
             'Microchip', 'Linear', 'Magellan', 'Paradox', 'Jarolift', 'Dooya',
             'BFT', 'FAAC', 'Marantec', 'Dickert', 'Beninca', 'Princeton']
    for mfr in known:
        if mfr.lower() in name.lower():
            return mfr
    first = name.split()[0] if name else ''
    if len(first) > 2 and first[0].isupper():
        return first
    return None


def main():
    print("Building unified RF protocol database...\n")

    rtl_json = load_rtl433_json()
    print(f"  [1] RTL_433 JSON: {len(rtl_json)} devices")
    rtl_src = parse_rtl433_sources()
    print(f"  [2] RTL_433 C sources: {len(rtl_src)} devices")
    urh_ng = parse_urh_ng()
    print(f"  [3] URH-NG: {len(urh_ng)} protocols")
    unleashed = parse_unleashed()
    print(f"  [4] Unleashed firmware: {len(unleashed)} protocols")
    zero_sploit = parse_sub_files(os.path.join(OTHER, 'FlipperZero-Subghz-DB', 'subghz'), 'zero_sploit')
    print(f"  [5] Zero-Sploit: {len(zero_sploit)} unique combos")
    uberguidoz = parse_sub_files(os.path.join(OTHER, 'Flipper', 'Sub-GHz'), 'uberguidoz')
    print(f"  [6] UberGuidoZ: {len(uberguidoz)} unique combos")
    rocketgod = parse_sub_files(os.path.join(OTHER, 'Flipper_Zero'), 'rocketgod')
    print(f"  [7] RocketGod: {len(rocketgod)} unique combos")
    skizzophrenic = parse_sub_files(os.path.join(OTHER, 'Ubers-SD-Files'), 'skizzophrenic')
    print(f"  [8] Skizzophrenic Ubers-SD: {len(skizzophrenic)} unique combos")
    wmbusmeters = parse_wmbusmeters()
    print(f"  [9] wmbusmeters: {len(wmbusmeters)} meter drivers")
    lillygo = parse_lillygo_sub()
    print(f"  [10] Lillygo SubGHz Signal: {len(lillygo)} unique combos")
    roguemaster = parse_rogumaster()
    print(f"  [11] RogueMaster (unique): {len(roguemaster)} protocols")
    keyfob = parse_keyfob_db()
    print(f"  [12] KeyfobDB: {len(keyfob)} automotive entries")
    rcswitch = parse_rc_switch()
    print(f"  [13] rc-switch: {len(rcswitch)} protocols")

    # Merge (priority order)
    all_devices, seen = [], set()
    for dev in urh_ng + unleashed + wmbusmeters + rtl_src + rtl_json + roguemaster + zero_sploit + uberguidoz + rocketgod + skizzophrenic + lillygo + keyfob + rcswitch:
        key = dev['name'].lower().strip()[:60]
        if key not in seen:
            seen.add(key)
            all_devices.append(dev)

    categories, sources = {}, {}
    for d in all_devices:
        categories[d.get('category', 'Other')] = categories.get(d.get('category', 'Other'), 0) + 1
        sources[d.get('source', '?')] = sources.get(d.get('source', '?'), 0) + 1

    output = {'version': '4.0.0', 'total_devices': len(all_devices), 'sources': sources, 'categories': categories, 'devices': all_devices}

    with open(OUTPUT, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['name','category','manufacturer','modulation','encoding','frequency','short_width','long_width','bits','checksum','source','device_id'])
        for d in all_devices:
            w.writerow([d.get(k,'') for k in ['name','category','manufacturer','modulation','encoding','frequency','short_width','long_width','bits','checksum','source','device_id']])

    if os.path.isdir(os.path.dirname(WM_OUTPUT)):
        with open(WM_OUTPUT, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        print(f"\n  -> WiFi Mothership updated")

    print(f"\n{'='*50}")
    print(f"UNIFIED DATABASE: {len(all_devices)} devices")
    print(f"{'='*50}")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cat}: {count}")
    print(f"\nSources:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")

if __name__ == '__main__':
    main()
