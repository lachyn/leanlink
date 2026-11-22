#!/usr/bin/env python3
"""Bit-perfect decoder for /cgi-bin/index.cgi?id=logcat dumps from LiaoYuan CPBox (V821B).

Reverse-engineered from `ota/www/cgi-bin/index.cgi` (`send_file` @ 0x11930):
1. Every 1024-byte output block is XOR-masked with the 14-byte key `b"liaoyuan.tech\\x00"`
   starting at index 0 of each 1024-byte block.
2. When `/tmp/log.gz` exceeds 1020 bytes, `send_file` splices the 32-bit little-endian
   original gzip byte length into bytes `[819:823]` of the first 1024-byte block
   (`fread(buf, 1, 819, fp); *(uint32_t*)(buf+819) = gz_len; fread(buf+823, 1, 201, fp)`),
   increasing HTTP Content-Length by 4 bytes.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

KEY = b"liaoyuan.tech\x00"


def decode_logcat(raw: bytes) -> str:
    dec = bytearray()
    for off in range(0, len(raw), 1024):
        chunk = raw[off : off + 1024]
        dec.extend(b ^ KEY[i % len(KEY)] for i, b in enumerate(chunk))

    if len(dec) >= 823:
        spliced_len = struct.unpack_from("<I", dec, 819)[0]
        if spliced_len == len(dec) - 4:
            dec = dec[:819] + dec[823:]

    try:
        plain = zlib.decompress(bytes(dec), 16 + zlib.MAX_WBITS)
    except zlib.error:
        # Fallback for truncated streams
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        out = bytearray()
        for off in range(0, len(dec), 256):
            try:
                out.extend(d.decompress(bytes(dec[off : off + 256])))
            except zlib.error:
                break
        plain = bytes(out)

    return plain.decode("utf-8", errors="replace")


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <logcat.gz> [output.txt]")
        raise SystemExit(1)
    decoded = decode_logcat(Path(sys.argv[1]).read_bytes())
    if len(sys.argv) >= 3:
        Path(sys.argv[2]).write_text(decoded, encoding="utf-8")
        print(f"Wrote {len(decoded):,} chars to {sys.argv[2]}")
    else:
        print(decoded)


if __name__ == "__main__":
    main()
