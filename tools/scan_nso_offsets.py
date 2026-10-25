"""Find every css_first hook and data offset in a Smash Ultimate main NSO.

Patterns are the instruction bytes around the sites src/lib.rs hooks. Branch
immediates are left out, because those change whenever a callee moves. Run
this on the next update's main and paste the printed values back into lib.rs.

  python tools/scan_nso_offsets.py <main-nso>

The NSO may be compressed. Requires the lz4 package. capstone is optional and
only used to print the instruction at each hook.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

TEXT_FLAG = 1
RO_FLAG = 2
DATA_FLAG = 4

# Call that passes the StageSelectScene hashed string in X1 (fp-0x88).
# The inline hook is the BL immediately after this setup.
SSS_TO_CSS_SETUP = bytes([
    0xE8, 0x0B, 0x00, 0xB9,  # str w8, [sp, #8]
    0x60, 0x12, 0x40, 0xF9,  # ldr x0, [x19, #0x20]
    0xA1, 0x23, 0x02, 0xD1,  # sub x1, x29, #0x88
    0xE2, 0x23, 0x00, 0x91,  # add x2, sp, #8
    0xA3, 0x03, 0x01, 0xD1,  # sub x3, x29, #0x40
])

# "CharaSelectS" built in X9, the literal the CSS->SSS hook rewrites.
# mov/movk pairs are the ASCII; the str between them is the stack slot.
CHARA_SELECT_SCENE = bytes([
    0x69, 0x08, 0x8D, 0xD2,  # mov  x9, #0x6843       "Ch"
    0x29, 0x4C, 0xAE, 0xF2,  # movk x9, #0x7261, lsl #16  "ar"
    0x29, 0x6C, 0xCA, 0xF2,  # movk x9, #0x5361, lsl #32  "aS"
    0xA9, 0x8C, 0xED, 0xF2,  # movk x9, #0x6c65, lsl #48  "el"
    0xE9, 0x07, 0x00, 0xF9,  # str  x9, [sp, #8]
    0xA9, 0x6C, 0x8C, 0xD2,  # mov  x9, #0x6365       "ec"
    0x89, 0x6E, 0xAA, 0xF2,  # movk x9, #0x5374, lsl #16  "tS"
])

# Argument setup for that call. The inline hook is the following BL.
CSS_TO_SSS_SETUP = bytes([
    0x60, 0x12, 0x40, 0xF9,  # ldr x0, [x19, #0x20]
    0xE1, 0x03, 0x00, 0x91,  # mov x1, sp
    0xE2, 0x63, 0x01, 0x91,  # add x2, sp, #0x58
    0xE3, 0x23, 0x01, 0x91,  # add x3, sp, #0x48
])

# register_panel_button prologue. Hook is the first instruction.
REGISTER_PANEL = bytes([
    0xFF, 0xC3, 0x05, 0xD1,  # sub sp, sp, #0x170
    0xFC, 0x5F, 0x13, 0xA9,  # stp x28, x23, [sp, #0x130]
    0xF6, 0x57, 0x14, 0xA9,  # stp x22, x21, [sp, #0x140]
    0xF4, 0x4F, 0x15, 0xA9,  # stp x20, x19, [sp, #0x150]
    0xFD, 0x7B, 0x16, 0xA9,  # stp x29, x30, [sp, #0x160]
    0xFD, 0x83, 0x05, 0x91,  # add x29, sp, #0x160
    0xE8, 0x04, 0x80, 0x92,  # mov x8, #-0x28
])

# hash40("se_system_r2f_fixed") = 0x13d3b19adc, then mov w2, #4; mov x1, x22.
# The play_se BL is 0x10 bytes after the first BL, and the inline hook is the
# instruction after that. The same shape follows the sudden-death hash.
SFX_R2F = bytes([
    0x96, 0x5B, 0x93, 0xD2,  # mov  x22, #0x9adc
    0x36, 0x76, 0xBA, 0xF2,  # movk x22, #0xd3b1, lsl #16
    0x76, 0x02, 0xC0, 0xF2,  # movk x22, #0x13, lsl #32
    0xE2, 0x03, 0x1E, 0x32,  # mov  w2, #4
    0xE1, 0x03, 0x16, 0xAA,  # mov  x1, x22
])
SFX_SUDDEN = bytes([
    0x36, 0x6C, 0x82, 0xD2,  # mov  x22, #0x1361       hash40("se_audience_suddendeath")
    0xD6, 0x60, 0xB4, 0xF2,  # movk x22, #0xa306, lsl #16
    0xF6, 0x02, 0xC0, 0xF2,  # movk x22, #0x17, lsl #32
    0xE2, 0x03, 0x1E, 0x32,  # mov  w2, #4
    0xE1, 0x03, 0x16, 0xAA,  # mov  x1, x22
])
MOV_X1_X22 = bytes([0xE1, 0x03, 0x16, 0xAA])

# Instructions immediately before the ADRP of the stage-select mode global.
# lib.rs reads the byte at this address + 3.
STAGE_MODE_ANCHOR = bytes([
    0x2B, 0x69, 0x6A, 0xF8,  # ldr x11, [x9, x10]
    0x6B, 0x01, 0x40, 0xB2,  # orr x11, x11, #1
    0x2B, 0x69, 0x2A, 0xF8,  # str x11, [x9, x10]
    0x09, 0x28, 0x40, 0xF9,  # ldr x9, [x0, #0x50]
])


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def find_all(haystack: bytes, needle: bytes) -> list[int]:
    hits = []
    start = 0
    while True:
        found = haystack.find(needle, start)
        if found < 0:
            return hits
        hits.append(found)
        start = found + 1


def decompress_segment(blob: bytes, decoded_size: int, compressed: bool) -> bytes:
    if not compressed:
        return blob[:decoded_size]
    import lz4.block

    return lz4.block.decompress(blob, uncompressed_size=decoded_size)


def load_nso(path: Path) -> dict:
    raw = path.read_bytes()
    if raw[:4] != b"NSO0":
        raise SystemExit(f"{path} is not an NSO (magic {raw[:4]!r})")
    flags = u32(raw, 0xC)
    segments = {}
    for name, base, flag in (("text", 0x10, TEXT_FLAG), ("ro", 0x20, RO_FLAG), ("data", 0x30, DATA_FLAG)):
        file_off = u32(raw, base)
        mem_off = u32(raw, base + 4)
        dec_size = u32(raw, base + 8)
        comp_size = u32(raw, 0x60 + (0 if name == "text" else 4 if name == "ro" else 8))
        blob = raw[file_off : file_off + comp_size]
        decoded = decompress_segment(blob, dec_size, bool(flags & flag))
        if len(decoded) != dec_size:
            raise SystemExit(f"{name} decoded to {len(decoded)} bytes, header says {dec_size}")
        segments[name] = {"mem": mem_off, "data": decoded}
    bss_size = u32(raw, 0x3C)
    image_size = segments["data"]["mem"] + len(segments["data"]["data"]) + bss_size
    return {
        "text": segments["text"]["data"],
        "ro_mem": segments["ro"]["mem"],
        "data_mem": segments["data"]["mem"],
        "data_end": segments["data"]["mem"] + len(segments["data"]["data"]),
        "bss_end": image_size,
    }


def section_of(nso: dict, off: int) -> str:
    if 0 <= off < nso["ro_mem"]:
        return "text"
    if nso["ro_mem"] <= off < nso["data_mem"]:
        return "rodata"
    if nso["data_mem"] <= off < nso["data_end"]:
        return "data"
    if nso["data_end"] <= off < nso["bss_end"]:
        return "bss"
    return "outside the image"


def is_bl(word: int) -> bool:
    return (word & 0xFC000000) == 0x94000000


def bl_target(off: int, word: int) -> int:
    imm = word & 0x3FFFFFF
    if imm & 0x2000000:
        imm -= 0x4000000
    return off + imm * 4


def bl_at(text: bytes, off: int) -> int | None:
    if off < 0 or off + 4 > len(text):
        return None
    word = u32(text, off)
    if not is_bl(word):
        return None
    return bl_target(off, word)


def adrp_page(off: int, word: int) -> int | None:
    if (word & 0x9F000000) != 0x90000000:
        return None
    immlo = (word >> 29) & 3
    immhi = (word >> 5) & 0x7FFFF
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm -= 1 << 21
    return (off & ~0xFFF) + (imm << 12)


def add_or_ldr_offset(word: int) -> int | None:
    if (word & 0xFF800000) == 0x91000000 and ((word >> 22) & 3) == 0:
        return (word >> 10) & 0xFFF
    if (word & 0xFFC00000) == 0xF9400000:
        return ((word >> 10) & 0xFFF) * 8
    if (word & 0xFFC00000) == 0xB9400000:
        return ((word >> 10) & 0xFFF) * 4
    return None


def address_after_anchor(text: bytes, anchor_end: int) -> int | None:
    """Decode the first ADRP + ADD/LDR pair in the next few instructions."""
    for off in range(anchor_end, min(anchor_end + 0x20, len(text) - 8), 4):
        word = u32(text, off)
        page = adrp_page(off, word)
        if page is None:
            continue
        reg = word & 0x1F
        follow = u32(text, off + 4)
        extra = add_or_ldr_offset(follow)
        if extra is None or ((follow >> 5) & 0x1F) != reg:
            continue
        return page + extra
    return None


def insn_at(text: bytes, off: int) -> str:
    if off < 0 or off + 4 > len(text):
        return ""
    try:
        from capstone import CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN, Cs
    except ImportError:
        return ""
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    decoded = list(md.disasm(text[off : off + 4], off))
    if not decoded:
        return ""
    insn = decoded[0]
    return f"{insn.mnemonic} {insn.op_str}".rstrip()


def report(name: str, off: int | None, note: str, text: bytes | None = None) -> None:
    if off is None:
        print(f"  {name:<24} missing  {note}")
        return
    shown = insn_at(text, off) if text is not None else ""
    extra = f"  {shown}" if shown else ""
    print(f"  {name:<24} 0x{off:x}  {note}{extra}")


def scene_call_after_string(text: bytes, string_at: int) -> int | None:
    """BL that consumes the hashed string built at string_at."""
    window_end = min(len(text), string_at + 0x180)
    window = text[string_at:window_end]
    found = []
    for rel in find_all(window, CSS_TO_SSS_SETUP):
        call = string_at + rel + len(CSS_TO_SSS_SETUP)
        if bl_at(text, call) is not None:
            found.append(call)
    if len(found) != 1:
        return None
    return found[0]


def sfx_site(text: bytes, needle: bytes) -> tuple[int | None, int | None, int | None]:
    """Return (nop BL, inline hook, play_se target) for one advance-SFX hash."""
    hits = find_all(text, needle)
    if len(hits) != 1:
        return None, None, None
    first_bl = hits[0] + len(needle)
    # hash; mov w2; mov x1; bl check; tbz; add/sub x0; mov x1, x22; bl play_se
    if bl_at(text, first_bl) is None:
        return None, None, None
    if text[first_bl + 0xC : first_bl + 0x10] != MOV_X1_X22:
        return None, None, None
    nop = first_bl + 0x10
    play = bl_at(text, nop)
    if play is None:
        return None, None, None
    return nop, nop + 4, play


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python tools/scan_nso_offsets.py <main-nso>")
    nso = load_nso(Path(sys.argv[1]))
    text = nso["text"]
    print(f"text 0x{len(text):x}  bss end 0x{nso['bss_end']:x}")
    print()
    print("code hooks")

    sss_hits = find_all(text, SSS_TO_CSS_SETUP)
    sss_call = None
    if len(sss_hits) == 1:
        candidate = sss_hits[0] + len(SSS_TO_CSS_SETUP)
        if bl_at(text, candidate) is not None:
            sss_call = candidate
    if sss_call is None and len(sss_hits) != 1:
        print(f"  {'sss_to_css':<24} {len(sss_hits)} setup hits")
    report("sss_to_css", sss_call, "inline hook, BL with StageSelectScene in X1", text)

    chara_hits = find_all(text, CHARA_SELECT_SCENE)
    css_call = scene_call_after_string(text, chara_hits[0]) if len(chara_hits) == 1 else None
    if css_call is None and len(chara_hits) != 1:
        print(f"  {'css_to_sss':<24} {len(chara_hits)} CharaSelectScene hits")
    report("css_to_sss", css_call, "inline hook, BL with CharaSelectScene in X1", text)

    sss_target = bl_at(text, sss_call) if sss_call is not None else None
    css_target = bl_at(text, css_call) if css_call is not None else None
    scene = sss_target if sss_target is not None and sss_target == css_target else None
    if sss_target is not None and css_target is not None and sss_target != css_target:
        print(f"  {'scene_transition':<24} callers disagree  sss->0x{sss_target:x} css->0x{css_target:x}")
    report("scene_transition", scene, "BL target of both scene rewrites", text)

    panel_hits = find_all(text, REGISTER_PANEL)
    panel = panel_hits[0] if len(panel_hits) == 1 else None
    if len(panel_hits) != 1:
        print(f"  {'register_panel_button':<24} {len(panel_hits)} prologue hits")
    report("register_panel_button", panel, "function entry", text)

    nop1, hook1, play1 = sfx_site(text, SFX_R2F)
    nop2, hook2, play2 = sfx_site(text, SFX_SUDDEN)
    report("css_advance_sfx_nop", nop1, "nop this BL", text)
    report("css_advance_sfx_hook", hook1, "inline hook after the nop", text)
    report("css_advance_sfx2_nop", nop2, "nop this BL", text)
    report("css_advance_sfx2_hook", hook2, "inline hook after the nop", text)
    play = play1 if play1 is not None and play1 == play2 else None
    if play1 is not None and play2 is not None and play1 != play2:
        print(f"  {'play_se':<24} callers disagree  sfx->0x{play1:x} sfx2->0x{play2:x}")
    report("play_se", play, "from_offset, BL target of both nops", text)

    print()
    print("data offsets")
    mode_hits = find_all(text, STAGE_MODE_ANCHOR)
    if len(mode_hits) != 1:
        print(f"  {'stage_select_mode':<24} {len(mode_hits)} anchor hits")
    else:
        addr = address_after_anchor(text, mode_hits[0] + len(STAGE_MODE_ANCHOR))
        if addr is None:
            print(f"  {'stage_select_mode':<24} anchor matched, ADRP not found")
        else:
            print(
                f"  {'stage_select_mode':<24} 0x{addr:x}  {section_of(nso, addr)}  "
                "lib.rs reads the byte at +3"
            )


if __name__ == "__main__":
    main()
