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

**Do not use with HDR** — HDR already includes this. If both are present, issues may happen.

## Requirements

- Smash Ultimate **13.0.3+**
- [Atmosphere](https://github.com/atmosphere-nx/atmosphere/releases) + [Skyline](https://github.com/skyline-dev/skyline)


# How to Build and Install
You must have Rust and Cargo installed. [Click here](https://www.rust-lang.org/tools/install) for instructions on how to install based on your system.

Once those are installed, open your command prompt or terminal and run the following commands
```sh
cargo install cargo-skyline
```

To compile your plugin use the following command in the root of the project (beside the `Cargo.toml` file):
```sh
cargo skyline build
```
Your resulting plugin will be the `.nro` found in the folder
```
[plugin name]/target/aarch64-skyline-switch
```
To install (you must already have skyline installed on your switch), put the plugin on your SD at:
```
sd:/atmosphere/contents/01006A800016E000/romfs/skyline/plugins
```

`cargo skyline` can also automate some of this process via FTP. If you have an FTP client on your Switch, you can run:
```sh
cargo skyline set-ip [Switch IP]
# install to the correct plugin folder on the Switch and listen for logs
cargo skyline run 
```

## Attribution

- Initial hooks: **blujay**
- Later maintenance / CSS-first fixes: **Brian Allred**, **jobrien97**, others

This standalone plugin is a minimal extract for players who want CSS-first without the full HDR package.

## License

AGPL-3.0-or-later (same family as HDR upstream). See `LICENSE` and `NOTICE.md`.
