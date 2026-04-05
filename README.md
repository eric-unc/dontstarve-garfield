# Garfield — Don't Starve Mod

Adds Garfield as a playable character in Don't Starve (base game + Reign of Giants).

## Character Overview

| Stat       | Value | Notes                                |
|------------|-------|--------------------------------------|
| Health     | 150   | Average — Garfield is not a fighter  |
| Hunger     | 250   | Loves food                           |
| Sanity     | 100   | Cynical worldview                    |
| Walk speed | ×0.9  | Lazy cat                             |
| Run speed  | ×0.9  | Still lazy                           |
| Hunger rate| ×1.25 | Eats more than Wilson                |

### Perks

- **Lasagna Lover** — Gets +20 bonus hunger when eating any cooked food.
  Eating Lasagna specifically triggers special dialogue.
- **Strong Stomach** — Can eat Monster Meat with no sanity penalty.
- **Lazy** — Slower movement, but not terribly so.

### Drawback

- **Monday Blues** — Every 7th game-day (days 1, 8, 15 …), Garfield takes
  −10 sanity at dawn and has his speed reduced by an additional 20% for that
  entire day.

### Special Recipe: Lasagna

Craft in the Crock Pot using **2+ meat + 1+ vegetable or fruit** (no inedible
filler). Yields one Lasagna with stats:

| Health | Hunger | Sanity | Perish |
|--------|--------|--------|--------|
| +20    | +75    | +20    | Medium |

Garfield also receives the +20 cooked-food bonus on top, for a total of +95
hunger when he eats it.

---

## File Structure

```
modinfo.lua                        — Mod metadata
modmain.lua                        — Entry point; registers character & recipe
scripts/
  prefabs/
    garfield.lua                   — Character prefab (stats, perks, Monday Blues)
    lasagna.lua                    — Lasagna food prefab
  speech_garfield.lua              — All of Garfield's examine/announce text
images/
  bigportraits/                    — 170×220 px in-game sidebar portrait
  saveslot_portraits/              — 62×62 px save-slot icon
  selectscreen_portraits/          — 260×226 px character select art
anim/
  garfield.zip                     — Character sprite build (see Art Assets below)
  ghost_garfield_build.zip         — Ghost sprite build
  lasagna.zip                      — Lasagna item sprite
```

---

## Art Assets (required to run in-game)

The Lua code is complete. To make the mod fully playable you need to supply
the binary art assets. Don't Starve uses `.tex` / `.xml` pairs for 2-D images
and compiled `.zip` animation bundles.

### Recommended toolchain

| Tool | Purpose |
|------|---------|
| [Ktools](https://github.com/nsimplex/ktools) | Convert PNG ↔ `.tex` / `.xml` and decompile/recompile `.zip` anim bundles |
| [Spriter](https://brashmonkey.com/spriter-pro/) | Edit character rigs and animation frames |
| Don't Starve mod tools (Steam > DS > Properties > DLC) | Automate texture atlas creation |

### Quick-start: reuse Wilson's build

To get a placeholder in-game quickly without custom art:

1. Extract Wilson's build from the game with ktools:
   ```
   ktech wilson.zip wilson/
   ```
2. Recolour the PNGs orange/brown to taste.
3. Repack as `garfield.zip` and `ghost_garfield_build.zip`.

### Image sizes

| File                                     | Width | Height |
|------------------------------------------|-------|--------|
| `images/bigportraits/garfield.tex`       | 170   | 220    |
| `images/saveslot_portraits/garfield.tex` | 62    | 62     |
| `images/selectscreen_portraits/garfield.tex` | 260 | 226  |
| `images/names_garfield.tex`              | varies | 30   |

After creating each PNG, run:
```
ktech garfield_portrait.png garfield.tex
```
This produces the `.tex` + `.xml` pair. Place both in the appropriate
`images/` subdirectory.

---

## Installation

1. Copy this folder to your Don't Starve mods directory:
   - **Windows:** `%USERPROFILE%\Documents\Klei\DoNotStarve\mods\`
   - **macOS:** `~/Library/Application Support/DoNotStarve/mods/`
   - **Linux:** `~/.klei/DoNotStarve/mods/`
2. Add the required art assets (see above).
3. Launch Don't Starve, go to **Mods**, enable **Garfield**, and start a new game.

---

## License

MIT — do whatever you want with it, just don't blame me when Garfield eats all your food supplies.
