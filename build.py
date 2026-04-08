"""Build unified RF protocol database from multiple sources."""
import json, os, re, glob

OUTPUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'data', 'rf_protocols_unified.json')

# === Source 1: Existing RTL_433 JSON (286 devices) ===
def load_rtl433_json():
    path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'data', 'rtl433_protocols.json')
    with open(path) as f:
        data = json.load(f)
    return data.get('devices', [])

# === Source 2: RTL_433 latest C source files ===
def parse_rtl433_sources():
    devices = []
    src_dir = os.path.expanduser('~/Desktop/GITHUBS/rtl_433/src/devices')
    if not os.path.isdir(src_dir):
        return devices
    for cfile in sorted(glob.glob(os.path.join(src_dir, '*.c'))):
        if 'new_template' in cfile:
            continue
        basename = os.path.splitext(os.path.basename(cfile))[0]
        with open(cfile, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # Extract device names from r_device structs
        for m in re.finditer(r'r_device\s+const\s+(\w+)\s*=\s*\{[^}]*\.name\s*=\s*"([^"]+)"', content, re.DOTALL):
            var_name, name = m.groups()
            # Try to extract modulation
            mod = 'OOK'
            if 'OOK_PULSE_PWM' in content or 'OOK_PULSE_PPM' in content:
                mod = 'OOK'
            if 'FSK_PULSE' in content:
                mod = 'FSK'
            # Try to extract short/long widths from the struct
            short_w = None
            long_w = None
            for sw in re.finditer(r'\.short_width\s*=\s*(\d+)', content):
                short_w = int(sw.group(1))
                break
            for lw in re.finditer(r'\.long_width\s*=\s*(\d+)', content):
                long_w = int(lw.group(1))
                break
            devices.append({
                'device_id': var_name,
                'name': name,
                'modulation': mod,
                'short_width': short_w,
                'long_width': long_w,
                'category': categorize_device(name),
                'manufacturer': extract_manufacturer(name),
                'source': 'rtl433_src',
                'source_file': basename + '.c',
            })
    return devices

# === Source 3: Zero-Sploit .sub file metadata ===
def parse_zero_sploit():
    devices = []
    base = os.path.expanduser('~/Desktop/GITHUBS/FlipperZero-Subghz-DB/subghz')
    if not os.path.isdir(base):
        return devices
    seen_categories = {}
    for category_dir in sorted(os.listdir(base)):
        cat_path = os.path.join(base, category_dir)
        if not os.path.isdir(cat_path):
            continue
        cat_name = category_dir.replace('_', ' ').replace('-', ' ').strip()
        sub_files = glob.glob(os.path.join(cat_path, '**', '*.sub'), recursive=True)
        # Extract unique frequency/modulation combos per category
        freq_mod_combos = {}
        for sf in sub_files:
            try:
                with open(sf, encoding='utf-8', errors='ignore') as f:
                    content = f.read(2000)  # Just read header
                freq = None
                preset = None
                protocol = None
                for line in content.split('\n'):
                    if line.startswith('Frequency:'):
                        freq = int(line.split(':')[1].strip())
                    elif line.startswith('Preset:'):
                        preset = line.split(':')[1].strip()
                    elif line.startswith('Protocol:'):
                        protocol = line.split(':')[1].strip()
                if freq and protocol and protocol != 'RAW':
                    key = f"{protocol}_{freq}"
                    if key not in freq_mod_combos:
                        freq_mod_combos[key] = {
                            'protocol': protocol,
                            'frequency': freq,
                            'preset': preset,
                            'count': 0,
                            'files': [],
                        }
                    freq_mod_combos[key]['count'] += 1
                    if len(freq_mod_combos[key]['files']) < 3:
                        freq_mod_combos[key]['files'].append(os.path.basename(sf))
            except:
                continue

        for key, info in freq_mod_combos.items():
            mod = 'OOK'
            if info['preset'] and ('2FSK' in info['preset'] or 'GFSK' in info['preset'] or 'MSK' in info['preset']):
                mod = 'FSK'
            devices.append({
                'device_id': f"zsploit_{info['protocol'].lower().replace(' ','_')}_{info['frequency']}",
                'name': f"{info['protocol']} ({cat_name})",
                'modulation': mod,
                'frequency': info['frequency'],
                'category': cat_name,
                'manufacturer': info['protocol'] if info['protocol'] != 'RAW' else None,
                'source': 'zero_sploit',
                'sample_count': info['count'],
                'sample_files': info['files'],
            })
    return devices

# === Source 4: URH-NG protocol list (parse markdown table) ===
def parse_urh_ng():
    devices = []
    path = os.path.expanduser('~/Desktop/GITHUBS/urh-ng/SUPPORTED_PROTOCOLS.md')
    if not os.path.isfile(path):
        return devices
    with open(path) as f:
        content = f.read()

    current_category = 'Unknown'
    for line in content.split('\n'):
        # Category headers
        cat_match = re.match(r'^## (.+?) \((\d+)\)', line)
        if cat_match:
            current_category = cat_match.group(1)
            continue
        # Table rows (skip header rows)
        if line.startswith('| ') and not line.startswith('| Protocol') and not line.startswith('|---'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 3:
                name = parts[0]
                modulation = parts[1] if len(parts) > 1 else ''
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
    return devices

def categorize_device(name):
    n = name.lower()
    if any(w in n for w in ['weather', 'rain', 'wind', 'barometer']):
        return 'Weather Station'
    if any(w in n for w in ['temperature', 'humidity', 'thermo', 'hygro', 'soil', 'pool']):
        return 'Temperature Sensor'
    if any(w in n for w in ['tpms', 'tire', 'tyre']):
        return 'TPMS'
    if any(w in n for w in ['garage', 'gate', 'came', 'nice', 'somfy', 'hormann', 'liftmaster', 'chamberlain']):
        return 'Gate/Garage'
    if any(w in n for w in ['doorbell', 'bell']):
        return 'Doorbell'
    if any(w in n for w in ['smoke', 'alarm', 'security', 'sensor', 'motion', 'window', 'door']):
        return 'Security/Alarm'
    if any(w in n for w in ['car key', 'key fob', 'keyfob', 'remote']):
        return 'Remote/Keyfob'
    if any(w in n for w in ['meter', 'ert', 'scm', 'water', 'gas', 'electric']):
        return 'Utility Meter'
    if any(w in n for w in ['bbq', 'meat', 'grill', 'kitchen']):
        return 'BBQ Thermometer'
    if any(w in n for w in ['blind', 'shade', 'curtain', 'automation']):
        return 'Home Automation'
    return 'Other'

def extract_manufacturer(name):
    known = ['Acurite', 'Oregon Scientific', 'LaCrosse', 'Fine Offset', 'Ambient Weather',
             'Bresser', 'ThermoPro', 'TFA', 'Honeywell', 'Schrader', 'Toyota', 'BMW',
             'Ford', 'Kia', 'Hyundai', 'Renault', 'Porsche', 'Subaru', 'Suzuki',
             'Chamberlain', 'LiftMaster', 'CAME', 'NICE', 'Somfy', 'Hormann',
             'Samsung', 'Philips', 'Nexus', 'Auriol', 'Eurochron', 'Rubicson',
             'Baldr', 'Inkbird', 'Kedsum', 'Danfoss', 'Watts', 'Vevor', 'Emos',
             'Microchip', 'Linear', 'Magellan', 'Paradox']
    for mfr in known:
        if mfr.lower() in name.lower():
            return mfr
    # Try first word
    first = name.split()[0] if name else ''
    if len(first) > 2 and first[0].isupper():
        return first
    return None

def main():
    print("Loading sources...")

    rtl_json = load_rtl433_json()
    print(f"  RTL_433 JSON: {len(rtl_json)} devices")

    rtl_src = parse_rtl433_sources()
    print(f"  RTL_433 sources: {len(rtl_src)} devices")

    zero_sploit = parse_zero_sploit()
    print(f"  Zero-Sploit: {len(zero_sploit)} unique protocol/freq combos")

    urh_ng = parse_urh_ng()
    print(f"  URH-NG: {len(urh_ng)} protocols")

    # Merge and deduplicate
    all_devices = []
    seen_names = set()

    # Priority: URH-NG (most structured) > RTL_433 src > RTL_433 JSON > Zero-Sploit
    for dev in urh_ng + rtl_src + rtl_json + zero_sploit:
        name_key = dev['name'].lower().strip()[:60]
        if name_key not in seen_names:
            seen_names.add(name_key)
            all_devices.append(dev)

    # Build category summary
    categories = {}
    for d in all_devices:
        cat = d.get('category', 'Other')
        categories[cat] = categories.get(cat, 0) + 1

    # Build source summary
    sources = {}
    for d in all_devices:
        src = d.get('source', 'unknown')
        sources[src] = sources.get(src, 0) + 1

    output = {
        'version': '2.0.0',
        'total_devices': len(all_devices),
        'sources': sources,
        'categories': categories,
        'devices': all_devices,
    }

    with open(OUTPUT, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nUnified database: {len(all_devices)} devices")
    print(f"Categories: {len(categories)}")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print(f"\nSources:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")
    print(f"\nSaved to: {OUTPUT}")

if __name__ == '__main__':
    main()
