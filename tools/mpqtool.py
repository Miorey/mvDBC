#!/usr/bin/env python3
"""mpqtool — minimal MPQ (format v1, WoW 3.3.5a) packer/reader. Python 3.9+, stdlib only.

Builds the client patch archives from build/client/<locale>/ instead of packing them by hand.
Archives are written as MPQ v1, zlib-compressed sectors, no encryption, with a (listfile).

Commands:
  pack    OUT.mpq DIR            pack every file under DIR (paths relative to DIR, e.g. DBFilesClient\\Spell.dbc)
  list    FILE.mpq               list the files of an archive (from its (listfile))
  extract FILE.mpq NAME OUT      extract one file, e.g. 'DBFilesClient\\Spell.dbc'
"""
import bz2
import os
import struct
import sys
import zlib

MPQ_FILE_IMPLODE = 0x00000100
MPQ_FILE_COMPRESS = 0x00000200
MPQ_FILE_ENCRYPTED = 0x00010000
MPQ_FILE_FIX_KEY = 0x00020000
MPQ_FILE_SINGLE_UNIT = 0x01000000
MPQ_FILE_SECTOR_CRC = 0x04000000
MPQ_FILE_EXISTS = 0x80000000


def _crypt_table():
    table = [0] * 0x500
    seed = 0x00100001
    for i in range(0x100):
        idx = i
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            t1 = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            t2 = seed & 0xFFFF
            table[idx] = t1 | t2
            idx += 0x100
    return table


CRYPT = _crypt_table()


def hash_string(s, htype):
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in s.upper().replace('/', '\\'):
        c = ord(ch)
        seed1 = (CRYPT[(htype << 8) + c] ^ (seed1 + seed2)) & 0xFFFFFFFF
        seed2 = (c + seed1 + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return seed1


def _crypt(data, key, decrypt):
    seed = 0xEEEEEEEE
    n = len(data) // 4
    words = list(struct.unpack('<%dI' % n, data[:n * 4]))
    for i in range(n):
        seed = (seed + CRYPT[0x400 + (key & 0xFF)]) & 0xFFFFFFFF
        w = words[i]
        out = (w ^ (key + seed)) & 0xFFFFFFFF
        plain = out if decrypt else w
        key = ((~key << 0x15) + 0x11111111 | (key >> 0x0B)) & 0xFFFFFFFF
        seed = (plain + seed + (seed << 5) + 3) & 0xFFFFFFFF
        words[i] = out
    return struct.pack('<%dI' % n, *words) + data[n * 4:]


def decrypt(data, key):
    return _crypt(data, key, True)


def encrypt(data, key):
    return _crypt(data, key, False)


class MPQ:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        off = 0
        while self.data[off:off + 4] != b'MPQ\x1a':
            off += 0x200
            if off >= len(self.data):
                raise ValueError('no MPQ header')
        self.base = off
        (_, hsize, _asize, fmt, ssh, ht_pos, bt_pos, ht_n, bt_n) = struct.unpack_from('<4sIIHHIIII', self.data, off)
        self.sector = 512 << ssh
        ht = decrypt(self.data[off + ht_pos:off + ht_pos + ht_n * 16], hash_string('(hash table)', 3))
        bt = decrypt(self.data[off + bt_pos:off + bt_pos + bt_n * 16], hash_string('(block table)', 3))
        self.hashes = [struct.unpack_from('<IIHHI', ht, i * 16) for i in range(ht_n)]
        self.blocks = [struct.unpack_from('<IIII', bt, i * 16) for i in range(bt_n)]

    def _find(self, name):
        n = len(self.hashes)
        a, b, start = hash_string(name, 1), hash_string(name, 2), hash_string(name, 0) % n
        i = start
        while True:
            h = self.hashes[i]
            if h[4] == 0xFFFFFFFF:
                return None
            if h[0] == a and h[1] == b and h[4] != 0xFFFFFFFE:
                return self.blocks[h[4]]
            i = (i + 1) % n
            if i == start:
                return None

    @staticmethod
    def _decompress(chunk):
        method, payload = chunk[0], chunk[1:]
        if method == 0x02:
            return zlib.decompress(payload)
        if method == 0x10:
            return bz2.decompress(payload)
        raise ValueError('unsupported compression 0x%02X' % method)

    def read(self, name):
        blk = self._find(name)
        if blk is None:
            return None
        pos, csize, fsize, flags = blk
        raw = self.data[self.base + pos:self.base + pos + csize]
        if flags & MPQ_FILE_ENCRYPTED:
            raise ValueError('encrypted files not supported')
        if flags & MPQ_FILE_IMPLODE:
            raise ValueError('imploded files not supported')
        if not flags & MPQ_FILE_COMPRESS:
            return raw[:fsize]
        if flags & MPQ_FILE_SINGLE_UNIT:
            return raw if csize >= fsize else self._decompress(raw)
        nsec = (fsize + self.sector - 1) // self.sector
        offs = struct.unpack_from('<%dI' % (nsec + 1), raw)
        out = bytearray()
        for s in range(nsec):
            chunk = raw[offs[s]:offs[s + 1]]
            want = min(self.sector, fsize - s * self.sector)
            out += chunk if len(chunk) >= want else self._decompress(chunk)
        return bytes(out)

    def names(self):
        lst = self.read('(listfile)')
        if lst is None:
            return []
        return [x for x in lst.decode('utf-8', 'replace').replace('\r', '').split('\n') if x]


def create(out_path, files):
    """files: list of (archive_name, bytes). zlib-compressed sectors, no encryption."""
    sector_shift = 3
    sector = 512 << sector_shift
    names = [n for n, _ in files]
    listfile = ('\r\n'.join(names) + '\r\n').encode()
    files = list(files) + [('(listfile)', listfile)]

    ht_n = 16
    while ht_n < len(files) * 2:
        ht_n *= 2

    body = bytearray()
    blocks = []
    header_size = 32
    for name, data in files:
        nsec = (len(data) + sector - 1) // sector or 1
        chunks = []
        for s in range(nsec):
            plain = data[s * sector:(s + 1) * sector]
            comp = b'\x02' + zlib.compress(plain, 9)
            chunks.append(comp if len(comp) < len(plain) else plain)
        offs = [4 * (nsec + 1)]
        for c in chunks:
            offs.append(offs[-1] + len(c))
        blob = struct.pack('<%dI' % (nsec + 1), *offs) + b''.join(chunks)
        blocks.append((header_size + len(body), len(blob), len(data), MPQ_FILE_EXISTS | MPQ_FILE_COMPRESS))
        body += blob

    hashes = [(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFF, 0xFFFF, 0xFFFFFFFF)] * ht_n
    for idx, (name, _) in enumerate(files):
        i = hash_string(name, 0) % ht_n
        while hashes[i][4] != 0xFFFFFFFF:
            i = (i + 1) % ht_n
        hashes[i] = (hash_string(name, 1), hash_string(name, 2), 0, 0, idx)

    ht = encrypt(b''.join(struct.pack('<IIHHI', *h) for h in hashes), hash_string('(hash table)', 3))
    bt = encrypt(b''.join(struct.pack('<IIII', *b) for b in blocks), hash_string('(block table)', 3))
    ht_pos = header_size + len(body)
    bt_pos = ht_pos + len(ht)
    archive_size = bt_pos + len(bt)
    header = struct.pack('<4sIIHHIIII', b'MPQ\x1a', header_size, archive_size, 0, sector_shift,
                         ht_pos, bt_pos, ht_n, len(blocks))
    with open(out_path, 'wb') as f:
        f.write(header + body + ht + bt)


def pack(out_path, directory):
    files = []
    for root, _, names in os.walk(directory):
        for name in sorted(names):
            path = os.path.join(root, name)
            arc = os.path.relpath(path, directory).replace(os.sep, '\\')
            with open(path, 'rb') as f:
                files.append((arc, f.read()))
    files.sort()
    if not files:
        sys.exit('nothing to pack in ' + directory)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    create(out_path, files)
    # Verify: every file must read back byte-identical.
    archive = MPQ(out_path)
    for arc, data in files:
        if archive.read(arc) != data:
            sys.exit('verification failed for ' + arc)
    print('packed %s (%d files)' % (out_path, len(files)))


def main(argv):
    if len(argv) < 3 or argv[1] not in ('pack', 'list', 'extract'):
        sys.exit(__doc__)
    cmd = argv[1]
    if cmd == 'pack' and len(argv) == 4:
        pack(argv[2], argv[3])
    elif cmd == 'list' and len(argv) == 3:
        archive = MPQ(argv[2])
        for name in archive.names():
            blk = archive._find(name)
            print('%-40s %10d bytes' % (name, blk[2]) if blk else name + '  (missing)')
    elif cmd == 'extract' and len(argv) == 5:
        data = MPQ(argv[2]).read(argv[3])
        if data is None:
            sys.exit('not found: ' + argv[3])
        with open(argv[4], 'wb') as f:
            f.write(data)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv)
