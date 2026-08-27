# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

"""komihash 5.0 — unsigned 64-bit hash.

Byte-exact port of hash4j ``0.30.0`` ``Hashing.komihash5_0()`` (seed 0).

Ported from the authoritative hash4j sources (tag ``v0.30.0``):
    com.dynatrace.hash4j.hashing.AbstractKomihash   # seed derivation + finish()
    com.dynatrace.hash4j.hashing.Komihash5_0        # hashBytesToLong(byte[],off,len)

This ports the one-shot ``hashBytesToLong`` path. hash4j guarantees the
streaming ``HashStream64`` result equals the one-shot hash of the concatenated
bytes, so building the full byte stream and hashing it once is sufficient (the
golden vectors, produced by the streaming Java API, confirm this empirically).

Java semantics reproduced here:
    * all arithmetic is on 64-bit values with wraparound  -> mask with MASK64
    * ``>>>`` is a logical (unsigned) shift; shift count uses the low 6 bits
      (long) / low 5 bits (int) of the amount  -> _ushr64 / _ushr32
    * ``unsignedMultiplyHigh`` = high 64 bits of the unsigned 128-bit product
"""

from __future__ import annotations

MASK64 = 0xFFFFFFFFFFFFFFFF
MASK32 = 0xFFFFFFFF

KOMIHASH_IMPLEMENTED = True


def _get_long(b: bytes, off: int) -> int:
    """Little-endian unsigned 64-bit read (hash4j ByteArrayUtil.getLong)."""
    return int.from_bytes(b[off : off + 8], "little")


def _get_int(b: bytes, off: int) -> int:
    """Little-endian unsigned 32-bit read (getInt masked with 0xFFFFFFFFL)."""
    return int.from_bytes(b[off : off + 4], "little")


def _umulh(a: int, b: int) -> int:
    """High 64 bits of the unsigned 128-bit product (unsignedMultiplyHigh)."""
    return ((a & MASK64) * (b & MASK64)) >> 64


def _ushr64(v: int, n: int) -> int:
    """Java ``long >>> n`` — logical shift, count masked to low 6 bits."""
    return (v & MASK64) >> (n & 63)


def _ushr32(v: int, n: int) -> int:
    """Java ``int >>> n`` — logical shift, count masked to low 5 bits."""
    return (v & MASK32) >> (n & 31)


def _seeds(seed: int) -> tuple[int, int, int, int, int, int, int, int]:
    """AbstractKomihash constructor seed derivation."""
    s1 = 0x243F6A8885A308D3 ^ (seed & 0x5555555555555555)
    s5 = 0x452821E638D01377 ^ (seed & 0xAAAAAAAAAAAAAAAA)
    lo = (s1 * s5) & MASK64
    h = _umulh(s1, s5)
    s5 = (s5 + h) & MASK64
    s1 = s5 ^ lo
    return (
        s1,
        0x13198A2E03707344 ^ s1,
        0xA4093822299F31D0 ^ s1,
        0x082EFA98EC4E6C89 ^ s1,
        s5,
        0xBE5466CF34E90C6C ^ s5,
        0xC0AC29B7C97C50DD ^ s5,
        0x3F84D5B5B5470917 ^ s5,
    )


def _finish(r1h: int, r2h: int, see5: int) -> int:
    """AbstractKomihash.finish(r1h, r2h, see5)."""
    see5 = (see5 + _umulh(r1h, r2h)) & MASK64
    see1 = see5 ^ ((r1h * r2h) & MASK64)
    r1h = _umulh(see1, see5)
    see1 = (see1 * see5) & MASK64
    see5 = (see5 + r1h) & MASK64
    see1 ^= see5
    return see1 & MASK64


def _hash_0_to_15(b: bytes, off: int, n: int, seed1: int, seed5: int) -> int:
    r1h = seed1
    r2h = seed5
    if n > 7:
        r1h ^= _get_long(b, off)
        ml8 = n << 3
        if n < 12:
            m = b[off + n - 3] | (b[off + n - 1] << 16) | (1 << 24) | (b[off + n - 2] << 8)
            ml8 ^= 24
            r2h ^= _ushr32(m, ml8)
        else:
            mh = _ushr64((_get_int(b, off + n - 4) | (1 << 32)), -ml8)
            ml = _get_int(b, off + 8)
            r2h ^= ((mh << 32) | ml) & MASK64
    elif n > 0:
        ml8 = n << 3
        if n < 4:
            r1h ^= (1 << ml8) & MASK64
            r1h ^= b[off]
            if n != 1:
                r1h ^= b[off + 1] << 8
                if n != 2:
                    r1h ^= b[off + 2] << 16
        else:
            mh = _ushr64((_get_int(b, off + n - 4) | (1 << 32)), -ml8)
            ml = _get_int(b, off)
            r1h ^= ((mh << 32) | ml) & MASK64
    return _finish(r1h & MASK64, r2h & MASK64, seed5)


def _hash_16_to_31(b: bytes, off: int, n: int, seed1: int, seed5: int) -> int:
    tmp1 = seed1 ^ _get_long(b, off)
    tmp2 = seed5 ^ _get_long(b, off + 8)
    see1 = (tmp1 * tmp2) & MASK64
    see5 = (seed5 + _umulh(tmp1, tmp2)) & MASK64
    see1 ^= see5
    ml8 = (n << 3) ^ 56
    if n < 24:
        r1h = _ushr64(_get_long(b, off + n - 8), 8) | (1 << 56)
        r2h = see5
        r1h = _ushr64(r1h, ml8) ^ see1
    else:
        r2h = _ushr64(_get_long(b, off + n - 8), 8) | (1 << 56)
        r1h = _get_long(b, off + 16) ^ see1
        r2h = _ushr64(r2h, ml8) ^ see5
    return _finish(r1h & MASK64, r2h & MASK64, see5)


def komihash5_0(data: bytes | bytearray, seed: int = 0) -> int:
    """Unsigned 64-bit komihash 5.0 of ``data`` (0 .. 2**64-1)."""
    b = bytes(data)
    n = len(b)
    seed1, seed2, seed3, seed4, seed5, seed6, seed7, seed8 = _seeds(seed)

    if n < 16:
        return _hash_0_to_15(b, 0, n, seed1, seed5)
    if n < 32:
        return _hash_16_to_31(b, 0, n, seed1, seed5)

    see1, see2, see3, see4 = seed1, seed2, seed3, seed4
    see5, see6, see7, see8 = seed5, seed6, seed7, seed8
    off = 0

    if n > 63:
        while n > 63:
            tmp1 = see1 ^ _get_long(b, off)
            tmp2 = see2 ^ _get_long(b, off + 8)
            tmp3 = see3 ^ _get_long(b, off + 16)
            tmp4 = see4 ^ _get_long(b, off + 24)
            tmp5 = see5 ^ _get_long(b, off + 32)
            tmp6 = see6 ^ _get_long(b, off + 40)
            tmp7 = see7 ^ _get_long(b, off + 48)
            tmp8 = see8 ^ _get_long(b, off + 56)

            see5 = (see5 + _umulh(tmp1, tmp5)) & MASK64
            see6 = (see6 + _umulh(tmp2, tmp6)) & MASK64
            see7 = (see7 + _umulh(tmp3, tmp7)) & MASK64
            see8 = (see8 + _umulh(tmp4, tmp8)) & MASK64

            see1 = see8 ^ ((tmp1 * tmp5) & MASK64)
            see2 = see5 ^ ((tmp2 * tmp6) & MASK64)
            see3 = see6 ^ ((tmp3 * tmp7) & MASK64)
            see4 = see7 ^ ((tmp4 * tmp8) & MASK64)

            off += 64
            n -= 64

        see5 ^= see6 ^ see7 ^ see8
        see1 ^= see2 ^ see3 ^ see4

    if n > 31:
        tmp1 = see1 ^ _get_long(b, off)
        tmp2 = see5 ^ _get_long(b, off + 8)
        see1 = (tmp1 * tmp2) & MASK64
        see5 = (see5 + _umulh(tmp1, tmp2)) & MASK64
        see1 ^= see5

        tmp3 = see1 ^ _get_long(b, off + 16)
        tmp4 = see5 ^ _get_long(b, off + 24)
        see1 = (tmp3 * tmp4) & MASK64
        see5 = (see5 + _umulh(tmp3, tmp4)) & MASK64
        see1 ^= see5
        off += 32
        n -= 32

    if n > 15:
        tmp1 = see1 ^ _get_long(b, off)
        tmp2 = see5 ^ _get_long(b, off + 8)
        see1 = (tmp1 * tmp2) & MASK64
        see5 = (see5 + _umulh(tmp1, tmp2)) & MASK64
        see1 ^= see5
        off += 16
        n -= 16

    ml8 = (n << 3) ^ 56
    if n < 8:
        r1h = _ushr64(_get_long(b, off + n - 8), 8) | (1 << 56)
        r2h = see5
        r1h = _ushr64(r1h, ml8) ^ see1
    else:
        r2h = _ushr64(_get_long(b, off + n - 8), 8) | (1 << 56)
        r1h = _get_long(b, off) ^ see1
        r2h = _ushr64(r2h, ml8) ^ see5

    return _finish(r1h & MASK64, r2h & MASK64, see5)
