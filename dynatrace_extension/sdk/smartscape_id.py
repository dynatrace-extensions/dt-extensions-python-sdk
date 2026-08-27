# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

"""Smartscape entity ID (long part) calculation.

The caller already knows an entity's **type** and its **id components** — the
ordered ``slot name -> value`` pairs that identify the entity. Pass the type
first, then the components as a mapping **in the rule's predefined order**:

    smartscape_id("TYPE", {"key1": "A", "key2": "B"})  # -> "TYPE-8B775215A352336E"

A ``dict`` (insertion-ordered) is the natural carrier for those pairs; the order
you insert them in is the order they are hashed, so it is significant.

Byte-stream contract:

    idLong = komihash5_0_seed0( STREAM ), signed to 64 bits

    STREAM =
        UTF-8(type) ++ int32_LE(len type)
        ++ int64_LE(keysHash)
        ++ for each value in component order: UTF-8(value) ++ int32_LE(len value)

    keysHash = komihash5_0_seed0(
        for each key in component order: UTF-8(key) ++ int32_LE(len key)
    )

Values are plain strings; ``len`` is the UTF-8 byte length.
"""

from __future__ import annotations

from collections.abc import Mapping

from .vendor.komihash import komihash5_0

MAX_VALUE_BYTES = 32768  # 32 KiB — matches SmartscapeIdCalculator.MAX_ALLOWED_VALUE_BYTE_LENGTH


def _feed_value(buf: bytearray, s: str) -> None:
    """Append a string as raw UTF-8 bytes then int32_LE(byte length).

    Equivalent to hash4j ``HashStream64.putByteArray``.
    """
    b = s.encode("utf-8")
    if len(b) > MAX_VALUE_BYTES:
        msg = f"value byte length {len(b)} exceeds allowed maximum {MAX_VALUE_BYTES}"
        raise ValueError(msg)
    buf += b
    buf += len(b).to_bytes(4, "little")


def _to_signed64(u: int) -> int:
    """Convert an unsigned 64-bit int to a Java signed long."""
    return u - 2**64 if u >= 2**63 else u


def _split(components: Mapping[str, str]) -> tuple[list[str], list[str]]:
    """Split the ordered id components into parallel key/value lists."""
    if not components:
        msg = "components must not be empty"
        raise ValueError(msg)
    return list(components.keys()), list(components.values())


def rule_keys_hash(keys: list[str]) -> int:
    """Unsigned 64-bit hash of the ordered component keys (the rule id).

    Stable per rule — compute once and cache keyed by the ordered key list.
    """
    if not keys:
        msg = "keys must not be empty"
        raise ValueError(msg)
    buf = bytearray()
    for k in keys:
        _feed_value(buf, k)
    return komihash5_0(buf)


def _entity_id_unsigned(type_: str, keys: list[str], values: list[str]) -> int:
    buf = bytearray()
    _feed_value(buf, type_)
    buf += rule_keys_hash(keys).to_bytes(8, "little")
    for v in values:
        _feed_value(buf, v)
    return komihash5_0(buf)


def smartscape_id_long(type_: str, components: Mapping[str, str]) -> int:
    """Smartscape entity ID long part as a Java signed long.

    :param type_: entity type string
    :param components: ordered ``slot name -> value`` id components; the mapping
        order must match the rule's predefined component order
    """
    keys, values = _split(components)
    return _to_signed64(_entity_id_unsigned(type_, keys, values))


def smartscape_id_hex(type_: str, components: Mapping[str, str]) -> str:
    """ID long part as a 16-digit upper-case hex string (the tenant rendering)."""
    keys, values = _split(components)
    return f"{_entity_id_unsigned(type_, keys, values):016X}"


def smartscape_id(type_: str, components: Mapping[str, str]) -> str:
    """Full Smartscape entity ID as rendered in the tenant: ``TYPE-<16 hex>``.

    :param type_: entity type string
    :param components: ordered ``slot name -> value`` id components; the mapping
        order must match the rule's predefined component order
    """
    return f"{type_}-{smartscape_id_hex(type_, components)}"
