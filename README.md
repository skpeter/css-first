# css_first

Skyline plugin for **Super Smash Bros. Ultimate** that puts **Character Select before Stage Select**.

Vanilla Versus order is Stage Select → Character Select. This plugin rewrites scene transitions so the flow becomes Character Select → Stage Select.

Logic copied from [HewDraw Remix](https://github.com/HDR-Development/HewDraw-Remix) (`sss_to_css` / `css_to_sss` / related cancel + CSS polish hooks).

## Install

1. Install [Skyline](https://github.com/skyline-dev/skyline) for Smash Ultimate.
2. Drop `libcss_first.nro` into:

```
atmosphere/contents/01006A800016E000/romfs/skyline/plugins/
```

3. Boot the game.

**Do not use with HDR** — HDR already includes this swap. Loading both will double-swap and restore vanilla order (or worse).

## Requirements

- Smash Ultimate **13.0.3+** (offsets from that generation)
- Atmosphere + Skyline

## Build

```sh
cargo install --git https://github.com/jam1garner/cargo-skyline --locked
cargo skyline update-std
cargo skyline build --release
```

Output:

```
target/aarch64-skyline-switch/release/libcss_first.nro
```

GitHub Actions builds the NRO on push and attaches it to GitHub Releases when you publish a release / push a `v*` tag.

## Attribution

Scene-order approach originated in HDR:

- Initial hooks: **blujay**
- Later maintenance / CSS-first fixes: **Brian Allred**, **jobrien97**, others

This standalone plugin is a minimal extract for players who want CSS-first without the full HDR package.

## License

AGPL-3.0-or-later (same family as HDR upstream). See `LICENSE` and `NOTICE.md`.
