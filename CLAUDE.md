# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Computer-vision auto-leveling bot for MapleStory Artale (MapleStory Worlds). It never touches game memory: it captures the game window, locates the player/mobs/runes with OpenCV template + HSV matching, and sends simulated keystrokes. Windows is the primary target (`windows-capture`, `pywin32`); macOS has a partial path (`GameWindowCapturorForMac`, `config_macOS.yaml`).

`PROJECT_STRUCTURE.md` (Traditional Chinese, untracked) holds a deeper architecture write-up including mermaid diagrams and the full route color-code table.

## Commands

```bash
pip install -r requirements.txt

python -m src.main                                  # GUI (primary entry point)
python -m src.engine.MapleStoryAutoLevelUp          # headless engine, defaults to --cfg custom
python -m src.engine.MapleStoryAutoLevelUp --cfg cleric --debug --disable_control --disable_viz
python -m tools.routeRecorder --new_map <map_dir>   # record map.png + route*.png
python tools/mob_maker.py                           # download mob sprites from maplestory.io GMS 65
python -m tools.AutoDiceRoller --attribute 4,4,13,4

build.bat                                           # pyinstaller one-file exe (also .github/workflows/build.yml on v* tags)
```

Useful engine flags: `--disable_control` (vision only, no keystrokes), `--test_image test/X.png` (feed a still instead of the live window), `--init_state solving_rune` (skip straight to a state).

Hotkeys while running: F1 pause/resume, F2 screenshot to `screenshot/`, F3 record (UI), F12 terminate. Logs go to `log/MSBot_<timestamp>.log` via the singleton `logger` in [src/utils/logger.py](src/utils/logger.py).

There is no test suite and no linter config. `tools/f_string_format_check.py` is a one-off regex scan for broken nested-quote f-strings.

## Architecture

### Two front-ends, one engine

`MapleStoryAutoBot` ([src/engine/MapleStoryAutoLevelUp.py](src/engine/MapleStoryAutoLevelUp.py), ~1900 lines) is the whole engine. It is driven either by:

- **GUI**: [src/main.py](src/main.py) then `MainWindow` ([src/ui/ui.py](src/ui/ui.py)) + `AutoBotController` ([src/ui/AutoBotController.py](src/ui/AutoBotController.py)). The controller is the only bridge; the UI never touches the bot directly. Debug frames reach the UI as Qt signals (`debug_image_signal`, `route_map_viz_signal`).
- **CLI**: `main()` at the bottom of the engine file acts as a "fake AutoBotController" — it re-implements config layering, thread startup, hotkey registration and the `cv2.imshow` debug loop.

Because of that duplication, **a new CLI arg must also be added to the fake `Namespace` in `AutoBotController.__init__`**, and config-loading changes must be made in both `main()` and `ui.py`.

### Threads

`bot.start()` spawns: keyboard-controller thread (`KeyBoardController`, holds `cmd_left_right`/`cmd_up_down`/`cmd_action` state and auto-casts buffs on cooldown), window-capture thread (`GameWindowCapturor`), `HealthMonitor` thread (independent HP/MP bar reading, potion keys, optional return-home scroll), and the bot `loop()` thread. `KeyBoardListener` runs a global hotkey hook. Qt owns the main thread. Keep heavy CV work off the Qt thread and out of the health monitor.

### Per-frame pipeline (`run_once`)

1. Grab frame from capture thread; if none, `activate_game_window()` and retry. After 30s with no minimap it assumes the login screen and clicks Login then character select.
2. `get_minimap_loc_size()` finds the minimap rect; `find_pattern_sqdiff` matches `img_minimap` against `minimaps/<map>/map.png` to get `loc_minimap_global`, combined with the yellow player dot to get `loc_player_global`.
3. On-screen player position: party red HP bar (HSV + geometry filter, preferred) or nametag template match (fallback, `nametag.enable`).
4. `fsm.do_state_stuff()` — the current state's `on_frame()` then `check_transitions()`.
5. State logic calls `update_cmd_by_route()` (reads route pixel colors near `loc_player_global`), `update_cmd_by_mob_detection()`, `is_player_stuck()`/watchdog, then pushes a `"<move_x> <move_y> <action>"` string into `kb.set_command()`.
6. Loop sleeps to hit `system.fps_limit_main`.

`Profiler.mark()` calls are sprinkled through `run_once`; keep them intact when editing that method.

### FSM

[src/engine/FiniteStateMachine.py](src/engine/FiniteStateMachine.py) is a plain name-to-`State` map with an allow-list of transitions and a 1-second minimum dwell time. States live in [src/states/](src/states/) and subclass `State` ([src/states/base_state.py](src/states/base_state.py)), each holding a back-reference to the bot. Registration is hardcoded in `MapleStoryAutoBot.__init__`: `hunting` to `finding_rune` to `near_rune`/`solving_rune` and back to `hunting`, plus the standalone `aux` and `patrol` modes (chosen by `bot.mode`, with no transitions in or out). Adding a state means adding both `add_state()` and the `add_transition()` edges there.

### Config layering

Merged in order, later overriding earlier (`override_cfg` in [src/utils/common.py](src/utils/common.py)):

1. `config/config_default.yaml` — the full schema with comments; **this is the only place a new setting key should be introduced**, since the Advanced Settings tab generates its widgets by walking this file (comments included, via `load_yaml_with_comments`).
2. `config/config_macOS.yaml` — auto-applied when `is_mac()`.
3. `config/config_<name>.yaml` — `--cfg <name>` (defaults to `custom`), or the file loaded in the GUI.

The GUI writes only the **diff** against the base config back to `config/config_custom.yaml` (`get_cfg_diff`), and dumps the fully merged config to `config/.config_tmp.yaml` before handing the path to `controller.start_bot()`. Both custom and tmp configs are gitignored.

`config/config_data.yaml` is separate data, not settings: `map_mobs_mapping` (which mob folders each map loads) and `eng_to_cn` translations. It is loaded directly in `MapleStoryAutoBot.__init__`, not merged.

`load_config()` returns `0`/`-1` rather than raising — callers check the return value.

### Assets as data

- `minimaps/<map_name>/map.png` plus `route1.png`, `route2.png`, ... — routes are *images*; each pixel color is an instruction looked up in `route.color_code` / `route.color_code_up_down` in `config_default.yaml` (e.g. `255,0,0` = move left, `255,255,0` = goal, which advances `idx_routes`, `255,0,127` = teleport up). `mask_route_colors()` blanks route pixels that collide with colors already present in `map.png`. `route_rest.png` is deliberately excluded from the route list.
- `monster/<mob_name>/<mob_name>*.png` — green (`0,255,0`) is the transparency key turned into a match mask; each sprite is also loaded mirrored.
- `nametag/`, `rune/`, `misc/` (language-suffixed UI button templates, `misc/..._{lang}.png` selected by `system.language`), `numbers/` (dice roller).

Adding a map = record with `routeRecorder`, drop the PNGs in `minimaps/<name>/`, register mobs under `map_mobs_mapping`, and add translations to `eng_to_cn`. Anything new the exe needs at runtime must also be added to the copy list in `.github/workflows/build.yml`.

### Resolution handling

Hardcoded pixel regions in the config (rune warning boxes, arrow box, login button, `ui_coords`) are authored for a 1282x693 window and rescaled at load time by `normalize_pixel_coordinate()` using `game_window.size`. New hardcoded coordinates should go through the same call in `load_config()`, and `game_window.size` in a custom config must match the real capture resolution or every region will be off.

### Legacy

`src/legacy/` and `config/legacy/` use the old full-screenshot camera localization (`maps/` instead of `minimaps/`). It is kept runnable but is not the maintained path — do not extend it.
