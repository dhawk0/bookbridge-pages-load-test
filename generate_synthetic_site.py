#!/usr/bin/env python3
"""Generate ONLY synthetic data for measuring GitHub Pages deployment capacity.

This script never reads a BookBridge database, manifest, or source archive.
"""
import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path

MIB = 1024 * 1024


def plans(scale):
    if scale == 'full':
        count = 17_845
        total = round(255.91 * MIB)
        largest = round(4.96 * MIB)
        manifest = round(1.76 * MIB)
        small_count = 12_000
        small_size = 1_024
    else:
        count = 64
        total = 2 * MIB
        largest = 128 * 1024
        manifest = 8 * 1024
        small_count = 40
        small_size = 1024
    medium_count = count - small_count - 1
    medium_total = total - largest - small_count * small_size
    if medium_count <= 0 or medium_total <= 0:
        raise ValueError('Invalid size distribution')
    medium_base, medium_remainder = divmod(medium_total, medium_count)
    sizes = ([small_size] * small_count +
             [medium_base + (1 if i < medium_remainder else 0)
              for i in range(medium_count)] + [largest])
    assert len(sizes) == count and sum(sizes) == total
    return sizes, manifest


def write_random_file(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with path.open('wb') as dest:
        remaining = size
        while remaining:
            piece = os.urandom(min(65536, remaining))
            dest.write(piece)
            h.update(piece)
            remaining -= len(piece)
    return h.hexdigest()


def make_manifest(size, count, shard_bytes, scale):
    core = {'schema': 'bookbridge-pages-load-1', 'synthetic_only': True,
            'scale': scale, 'source_records_included': 0,
            'shards': count, 'synthetic_shard_bytes': shard_bytes,
            'padding': ''}
    padding_len = size - len(json.dumps(core, separators=(',', ':'), sort_keys=True).encode())
    if padding_len < 0:
        raise ValueError('Manifest target too small')
    # Base64 characters keep the manifest valid UTF-8 JSON, without carrying source data.
    core['padding'] = base64.b64encode(os.urandom((padding_len * 3 + 3) // 4)).decode()[:padding_len]
    b = json.dumps(core, separators=(',', ':'), sort_keys=True).encode()
    assert len(b) == size
    return b


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--scale', choices=['smoke', 'full'], required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    out = args.output.resolve()
    if out.exists() and any(out.iterdir()):
        ap.error('Output directory must be empty: ' + str(out))
    out.mkdir(parents=True, exist_ok=True)
    sizes, manifest_size = plans(args.scale)
    began = time.monotonic()
    probes = {}
    shard_bytes = sum(sizes)
    for i, size in enumerate(sizes):
        name = f'shards/{i // 1000:03d}/s{i:05d}.bin'
        checksum = write_random_file(out / name, size)
        if i in (0, len(sizes) - 1):
            probes['first' if i == 0 else 'largest'] = {
                'path': name, 'bytes': size, 'sha256': checksum
            }
        if (i + 1) % 5000 == 0:
            print(f'Generated {i+1:,} synthetic shards', flush=True)

    (out / 'manifest.json').write_bytes(make_manifest(
        manifest_size, len(sizes), shard_bytes, args.scale))
    health = {
        'schema': 'bookbridge-pages-load-health-1',
        'synthetic_only': True,
        'source_records_included': 0,
        'purpose': 'GitHub Pages deployment size and file-count test only',
        'scale': args.scale,
        'shards': len(sizes),
        'shard_bytes': shard_bytes,
        'manifest_bytes': manifest_size,
        'probes': probes
    }
    (out / 'health.json').write_text(json.dumps(health, indent=2) + '\n', encoding='utf-8')
    site_index = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BookBridge | Synthetic Pages Load Test</title>
<style>body{font-family:system-ui,sans-serif;max-width:750px;margin:55px auto;padding:0 18px;line-height:1.6}
button{background:#285b46;color:white;border:0;border-radius:6px;padding:12px 18px;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f4f4;color:#222;padding:16px}</style></head>
<body><h1>BookBridge — Synthetic GitHub Pages Load Test</h1>
<p><strong>NO REAL BOOK RECORDS.</strong> This site consists entirely of random bytes for technical deployment testing.</p>
<p id="summary">Loading synthetic site summary…</p>
<button id="test">Verify first and largest static shard</button><pre id="result">Not tested.</pre>
<script>
const $=id=>document.getElementById(id);let h;
async function load(){const r=await fetch('./health.json',{cache:'no-store'});if(!r.ok)throw Error(`health HTTP ${r.status}`);
h=await r.json();if(!h.synthetic_only||h.source_records_included!==0)throw Error('Synthetic-only manifest check failed');
$('summary').textContent=`${h.shards.toLocaleString()} synthetic shards; ${(h.shard_bytes/1048576).toFixed(2)} MiB synthetic shard data; ${h.scale} deployment.`;}
$('test').addEventListener('click',async()=>{try {if(!h)await load();let lines=[];
for(const [name,p] of Object.entries(h.probes)){
const start=performance.now();const r=await fetch('./'+p.path,{cache:'no-store'});if(!r.ok)throw Error(`${name}: HTTP ${r.status}`);
const b=await r.arrayBuffer();if(b.byteLength!==p.bytes)throw Error(`${name}: size mismatch`);
const digest=await crypto.subtle.digest('SHA-256',b);const hex=Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');
if(hex!==p.sha256)throw Error(`${name}: SHA-256 mismatch`);
lines.push(`PASS ${name}: ${b.byteLength.toLocaleString()} bytes in ${Math.round(performance.now()-start)} ms`);
} $('result').textContent=lines.join('\n');
}catch(e){$('result').textContent='FAIL: '+e.message;}});
load().catch(e=>{$('summary').textContent='Cannot load summary: '+e.message;});
</script></body></html>'''
    (out / 'index.html').write_text(site_index, encoding='utf-8')
    files = sum(1 for p in out.rglob('*') if p.is_file())
    total_bytes = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert files == len(sizes) + 3
    print(json.dumps({
        'state': 'SYNTHETIC_SITE_BUILT', 'synthetic_only': True,
        'real_records_included': 0,
        'scale': args.scale, 'shards': len(sizes),
        'site_files': files, 'shard_mib': round(shard_bytes/MIB, 2),
        'site_mib': round(total_bytes/MIB, 2),
        'output': str(out), 'elapsed_seconds': round(time.monotonic()-began, 1)
    }, indent=2), flush=True)


if __name__ == '__main__':
    main()
