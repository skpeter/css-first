//! CSS First — swap Smash Ultimate Versus flow so Character Select runs before Stage Select.
//!
//! Extracted from HDR (HewDraw-Remix) scene-transition hooks.
//! Offsets target game version 13.0.3+.
//!
//! Do not load alongside HDR — HDR already installs the same swap.

#![feature(proc_macro_hygiene)]

use skyline::hooks::InlineCtx;
use skyline::libc::{c_char, c_void};

#[repr(C)]
struct HashedString {
    length: u32,
    hash: u32,
    string: [u8; 64],
}

impl HashedString {
    fn set(&mut self, replacement: &str) {
        self.length = replacement.len() as u32;
        self.string[..replacement.len()].copy_from_slice(replacement.as_bytes());
        self.string[replacement.len()] = b'\0';
    }

    fn as_str(&self) -> &str {
        let len = self
            .string
            .iter()
            .position(|&c| c == 0)
            .unwrap_or(self.string.len());
        std::str::from_utf8(&self.string[..len]).unwrap_or("")
    }
}

static mut CSS_FIRST: bool = false;
static mut SSS_CANCEL_TO_CSS: bool = false;
static mut CSS_CANCEL_TO_LOCAL: bool = false;
static mut IN_LOCAL_WIRELESS: bool = false;

/// Vanilla wants Stage Select first — rewrite destination to Character Select.
#[skyline::hook(offset = 0x23357f8, inline)]
unsafe fn sss_to_css(ctx: &InlineCtx) {
    let hashed_string = ctx.registers[1].x() as *mut HashedString;
    let current_scene = (*hashed_string).as_str();

    if current_scene == "StageSelectScene" {
        CSS_FIRST = true;
        (*hashed_string).set("CharaSelectScene");
        CSS_CANCEL_TO_LOCAL = IN_LOCAL_WIRELESS;
    }
}

/// After Character Select, send players to Stage Select (when SSS applies).
#[skyline::hook(offset = 0x2335184, inline)]
unsafe fn css_to_sss(ctx: &InlineCtx) {
    let hashed_string = ctx.registers[1].x() as *mut HashedString;
    let current_scene = (*hashed_string).as_str();

    if current_scene == "CharaSelectScene" {
        let text = skyline::hooks::getRegionAddress(skyline::hooks::Region::Text) as u64;
        let flag_ptr = (text + 0x530996c) as *const u8;
        let flag = *flag_ptr.add(3);

        // Stage select modes 0/1/2 show SSS; 3/4 skip it.
        if flag <= 2 {
            (*hashed_string).set("StageSelectScene");
            SSS_CANCEL_TO_CSS = IN_LOCAL_WIRELESS;
        } else {
            CSS_FIRST = false;
        }
    }
}

/// Fix back/cancel paths when CSS is first (esp. local wireless).
#[skyline::hook(offset = 0x3726120)]
unsafe fn scene_transition(
    list_ptr: *mut c_void,
    key_struct: *const HashedString,
    context_struct: *const HashedString,
    factory: *mut c_void,
) {
    if !key_struct.is_null() {
        let str_ptr = (key_struct as *const u8).add(8) as *const c_char;
        let initial_key = skyline::from_c_str(str_ptr);

        if SSS_CANCEL_TO_CSS && initial_key == "MeleeRuleScene" {
            (*(key_struct as *mut HashedString)).set("CharaSelectScene");
            SSS_CANCEL_TO_CSS = false;
        } else if CSS_CANCEL_TO_LOCAL && initial_key == "MeleeRuleScene" {
            (*(key_struct as *mut HashedString)).set("LocalTopScene");
            CSS_CANCEL_TO_LOCAL = false;
        }

        let key_str = skyline::from_c_str((key_struct as *const u8).add(8) as *const c_char);

        if key_str == "MeleeRuleScene" || key_str == "MainMenuScene" {
            CSS_FIRST = false;
        }

        if key_str.starts_with("Local") {
            IN_LOCAL_WIRELESS = true;
        } else if key_str == "MainMenuScene" || key_str == "MenuSequenceScene" {
            IN_LOCAL_WIRELESS = false;
        }

        if key_str != "StageSelectScene"
            && key_str != "CharaSelectScene"
            && key_str != "MeleeRuleScene"
        {
            SSS_CANCEL_TO_CSS = false;
            CSS_CANCEL_TO_LOCAL = false;
        }
    }

    call_original!(list_ptr, key_struct, context_struct, factory);
}

/// Hide Rules on CSS when CSS is first — button otherwise dumps to main menu.
#[skyline::hook(offset = 0x3771220)]
unsafe fn register_panel_button(
    panel: *mut u64,
    event_code: i32,
    name: *const c_char,
    arg4: u64,
    arg5: u64,
    arg6: u64,
    arg7: u64,
    arg8: u64,
) {
    if CSS_FIRST && !name.is_null() && skyline::from_c_str(name as *const u8) == "set_btn_03_rule" {
        return;
    }
    call_original!(panel, event_code, name, arg4, arg5, arg6, arg7, arg8);
}

#[skyline::from_offset(0x2407280)]
unsafe fn play_se(param_1: *mut u32, sfx_hash_id: u64);

#[skyline::hook(offset = 0x1a2d440, inline)]
unsafe fn css_advance_sfx_hook(ctx: &mut InlineCtx) {
    // se_system_amiibo_write_2 vs se_system_r2f_fixed
    let param_1 = ctx.registers[0].x() as *mut u32;
    let sfx = if CSS_FIRST {
        0x18d72a665a_u64
    } else {
        0x13d3b19adc_u64
    };
    play_se(param_1, sfx);
}

#[skyline::hook(offset = 0x1a2d594, inline)]
unsafe fn css_advance_sfx2_hook(ctx: &mut InlineCtx) {
    if !CSS_FIRST {
        // se_audience_suddendeath
        let sfx = 0x17a3061361_u64;
        let param_1 = ctx.registers[0].x() as *mut u32;
        play_se(param_1, sfx);
    }
}

#[skyline::main(name = "css_first")]
pub fn main() {
    println!("[css_first] installing CSS-before-SSS scene swap");
    skyline::install_hooks!(
        sss_to_css,
        css_to_sss,
        scene_transition,
        register_panel_button,
        css_advance_sfx_hook,
        css_advance_sfx2_hook,
    );
    // Silence default CSS advance SFX; hooks above play the right one.
    skyline::patching::Patch::in_text(0x1a2d43c).nop().unwrap();
    skyline::patching::Patch::in_text(0x1a2d590).nop().unwrap();
    println!("[css_first] ready");
}
