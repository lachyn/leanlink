#!/usr/bin/env python3
"""OTA container helpers for LeanLink (cpbox-abroad platform, Allwinner V821B).

Covers exactly what tools/build_patched_ota.py needs:

* V821 XOR encryption of the whole update.img (byte i ^= key[i & 0xFF]);
* the "<md5>  update.swu\\n" envelope in front of the SWUpdate archive;
* SVR4 "newc" CPIO archives (magic 070701, and 070702 with checksum) that parse and re-pack
  byte-identically, including the trailing padding (4096 B on ly6071, 512 B on ly5140);
* SquashFS superblock inspection (block size, mkfs_time, inode count);
* sw-description checks (magic 0xAA55A55A, ly_project_name).

The XOR key and the OTA layout were first documented by the CatPlay project.
Standard library only.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
import struct

__all__ = [
    "V821_KEY",
    "OtaError",
    "xor_v821",
    "decrypt",
    "encrypt",
    "unwrap_envelope",
    "wrap_envelope",
    "CpioMember",
    "CpioArchive",
    "SquashfsInfo",
    "squashfs_info",
    "validate_sw_description",
]

# 256-byte XOR key shared by the V821 cpbox-abroad projects.
V821_KEY = bytes.fromhex(
    "1269544837f0d56e927e26c3e525c5ee2a968b51ab10f2a9dc1d1b54b2a0a4b5"
    "faf8fd31e9d2a07b50c63e36eb03246613bfb73fc0a9e89cc704f079a4952e9e"
    "7e3bd077fd70f24e3630842133a887c77742e40df6f32c895249915fbe9164e0"
    "af2d03c12bd809974759061c808fbd48b1a155c8958151e7cbe2478974ab6a13"
    "696dd40445de9b8d37a2a9b73167ff02375e0617e8eeb4aff2a42897395735c7"
    "62053e807530ceab6052cd94fa545b513361697b4f1d2a42c152d9fba90ec22c"
    "2401ac89317a3592cc0226c6568117e94ca0ba4346b40f2e925f1d080d750005"
    "620dc92322fdd4486c6f4f6fd52788a108a5ca9dd61b85a1fecc2b7277958550"
)
assert len(V821_KEY) == 256


class OtaError(RuntimeError):
    """The image does not have the expected structure."""


# --------------------------------------------------------------------------- encryption

def xor_v821(data: bytes) -> bytes:
    """XOR every byte with V821_KEY[offset & 0xFF] (the operation is its own inverse)."""
    n = len(data)
    if n == 0:
        return b""
    stream = (V821_KEY * (n // 256 + 1))[:n]
    value = int.from_bytes(data, "little") ^ int.from_bytes(stream, "little")
    return value.to_bytes(n, "little")


def _require_trailer(plain: bytes) -> None:
    """A correctly decrypted image ends with an empty CRC-format TRAILER!!! entry plus zero padding."""
    pos = plain.rfind(b"TRAILER!!!\0")
    if pos < 110:
        raise OtaError("no CPIO TRAILER!!! entry (wrong key or not an OTA image)")
    head = plain[pos - 110 : pos]
    if head[:6] != b"070702" or int(head[54:62], 16) != 0 or int(head[94:102], 16) != 11:
        raise OtaError("last CPIO entry is not an empty 070702 TRAILER!!!")
    if any(plain[pos + 11 :]):
        raise OtaError("non-zero bytes after the CPIO trailer")


def decrypt(image: bytes) -> bytes:
    """Encrypted update.img -> plaintext (envelope + archive)."""
    plain = xor_v821(image)
    _require_trailer(plain)
    return plain


def encrypt(plain: bytes) -> bytes:
    """Plaintext (envelope + archive) -> encrypted update.img."""
    _require_trailer(plain)
    return xor_v821(plain)


# --------------------------------------------------------------------------- envelope

_ENVELOPE = re.compile(rb"([0-9a-fA-F]{32})  update\.swu\n")


def unwrap_envelope(plain: bytes) -> bytes:
    """Strip and verify the "<md5>  update.swu\\n" line; returns the SWUpdate archive."""
    m = _ENVELOPE.match(plain)
    if not m:
        raise OtaError('missing "<md5>  update.swu" header')
    swu = plain[m.end() :]
    digest = hashlib.md5(swu).hexdigest()
    if digest != m.group(1).decode("ascii").lower():
        raise OtaError(f"archive MD5 mismatch ({digest} != {m.group(1).decode()})")
    return swu


def wrap_envelope(swu: bytes) -> bytes:
    return hashlib.md5(swu).hexdigest().encode("ascii") + b"  update.swu\n" + swu


# --------------------------------------------------------------------------- CPIO

_HDR = 110
_FIELDS = ("ino", "mode", "uid", "gid", "nlink", "mtime", "filesize",
           "devmajor", "devminor", "rdevmajor", "rdevminor", "namesize", "check")
_PADDINGS = (4096, 512)  # archive end padding used by the vendor (largest first)


def _pad4(n: int) -> int:
    return (n + 3) & ~3


@dataclasses.dataclass
class CpioMember:
    magic: bytes            # b"070701" or b"070702"
    name: str
    header: dict[str, int]  # all 13 numeric header fields as read
    data: bytes


class CpioArchive:
    """newc / CRC CPIO archive as used by SWUpdate (.swu)."""

    def __init__(self, members: list[CpioMember], padding: int) -> None:
        self.members = members
        self.padding = padding

    @classmethod
    def parse(cls, raw: bytes) -> "CpioArchive":
        members: list[CpioMember] = []
        pos = 0
        while True:
            head = raw[pos : pos + _HDR]
            if len(head) < _HDR:
                raise OtaError(f"truncated CPIO header at {pos}")
            magic = head[:6]
            if magic not in (b"070701", b"070702"):
                raise OtaError(f"bad CPIO magic {magic!r} at {pos}")
            try:
                values = [int(head[6 + 8 * i : 14 + 8 * i], 16) for i in range(13)]
            except ValueError:
                raise OtaError(f"non-hex CPIO header at {pos}") from None
            hdr = dict(zip(_FIELDS, values))
            name_end = pos + _HDR + hdr["namesize"]
            if hdr["namesize"] < 1 or name_end > len(raw) or raw[name_end - 1] != 0:
                raise OtaError(f"bad CPIO name at {pos}")
            name = raw[pos + _HDR : name_end - 1].decode("utf-8")
            start = _pad4(name_end)
            end = start + hdr["filesize"]
            if end > len(raw):
                raise OtaError(f"truncated CPIO data of {name}")
            data = raw[start:end]
            if magic == b"070702" and sum(data) & 0xFFFFFFFF != hdr["check"]:
                raise OtaError(f"CPIO checksum mismatch in {name}")
            members.append(CpioMember(magic, name, hdr, data))
            pos = _pad4(end)
            if name == "TRAILER!!!":
                break

        if any(raw[pos:]):
            raise OtaError("non-zero data after the CPIO trailer")
        padding = next((p for p in _PADDINGS if len(raw) % p == 0 and len(raw) - pos < p), None)
        if padding is None:
            raise OtaError("archive end is not padded to 512 or 4096 bytes")
        names = [m.name for m in members]
        if names[0] != "sw-description":
            raise OtaError("sw-description must be the first member")
        if len(set(names)) != len(names):
            raise OtaError("duplicate CPIO member names")
        archive = cls(members, padding)
        if archive.pack() != raw:
            raise OtaError("CPIO archive does not re-pack byte-identically")
        return archive

    def _find(self, name: str) -> CpioMember:
        found = [m for m in self.members if m.name == name]
        if len(found) != 1:
            raise OtaError(f"expected one CPIO member {name!r}, found {len(found)}")
        return found[0]

    def member(self, name: str) -> bytes:
        return self._find(name).data

    def replace(self, name: str, data: bytes) -> None:
        self._find(name).data = data

    def pack(self) -> bytes:
        out = bytearray()
        for m in self.members:
            name = m.name.encode("utf-8") + b"\0"
            hdr = dict(m.header, filesize=len(m.data), namesize=len(name),
                       check=(sum(m.data) & 0xFFFFFFFF) if m.magic == b"070702" else 0)
            out += m.magic + b"".join(b"%08X" % hdr[f] for f in _FIELDS) + name
            out += bytes(-len(out) % 4)
            out += m.data
            out += bytes(-len(out) % 4)
        out += bytes(-len(out) % self.padding)
        return bytes(out)


# --------------------------------------------------------------------------- SquashFS

@dataclasses.dataclass(frozen=True)
class SquashfsInfo:
    inodes: int
    mkfs_time: int
    block_size: int
    compression: int  # 4 = xz
    bytes_used: int


def squashfs_info(blob: bytes) -> SquashfsInfo:
    """Read the SquashFS 4.0 superblock (little endian) and check what the vendor image uses."""
    if len(blob) < 96 or blob[:4] != b"hsqs":
        raise OtaError("not a little-endian SquashFS image")
    inodes, mkfs_time, block_size = struct.unpack_from("<III", blob, 4)
    compression, = struct.unpack_from("<H", blob, 20)
    major, minor = struct.unpack_from("<HH", blob, 28)
    bytes_used, = struct.unpack_from("<Q", blob, 40)
    xattr_table, = struct.unpack_from("<Q", blob, 56)
    info = SquashfsInfo(inodes, mkfs_time, block_size, compression, bytes_used)
    if (major, minor) != (4, 0):
        raise OtaError(f"unsupported SquashFS version {major}.{minor}")
    if compression != 4:
        raise OtaError(f"SquashFS is not xz-compressed: {info}")
    if xattr_table != 0xFFFFFFFFFFFFFFFF:
        raise OtaError("SquashFS carries xattrs, which a repack would drop")
    if bytes_used > len(blob):
        raise OtaError("SquashFS image is truncated")
    return info


# --------------------------------------------------------------------------- sw-description

def validate_sw_description(blob: bytes, project: str) -> None:
    """Check that sw-description is a vendor V821 one for `project` (e.g. "ly5140")."""
    text = blob.decode("utf-8")
    if not re.search(r'\bmagic\s*=\s*"0xAA55A55A"\s*;', text):
        raise OtaError('sw-description lacks magic = "0xAA55A55A"')
    m = re.search(r'\bly_project_name\s*=\s*"(ly\d+)"\s*;', text)
    if not m or m.group(1) != project:
        raise OtaError(f"sw-description is for {m.group(1) if m else 'no project'}, expected {project}")
    for needle in ('filename = "kernel"', 'device = "/dev/by-name/boot"',
                   'filename = "customer"', 'device = "/dev/by-name/customer"'):
        if needle not in text:
            raise OtaError(f"sw-description has an unexpected layout (missing {needle})")
