# ClashofClansInviteBot: context for Claude

Recruiting bot for my Clash of Clans clan (**#2RC8GRG80**). Goal: invite thousands of
well-chosen players a day. Think "personalized advertising": find the players most likely
to join, using the official CoC API, then invite them in-game through BlueStacks over ADB.

I'm a CS student, comfortable with Python. I'm a visual learner, so use diagrams, tables and
clean formatting when explaining.

## Environment
- MacBook Air (Apple Silicon), BlueStacks Air with Clash of Clans, ADB at `127.0.0.1:5555`
  (`brew install android-platform-tools`). Python venv in `.venv/`.
- You can run the bot and `adb` yourself. Test the invite flow directly instead of asking me.
- Running the in-game automation breaks Supercell's ToS. Use an alt/expendable account.
- The old `COC_TOKEN` was committed to git history (leaked). Use a fresh key in `.env` (gitignored).

## What exists today (`python.py`)
Original bot: walks the in-game Clans tab and invites members clan by clan.
- `--adb` mode (the one to use): `Adb` class sends input straight into Android, so my mouse
  stays free and BlueStacks can sit behind other windows.
  - `tap(rel)` → `adb shell input tap`
  - `swipe()` → `input motionevent` DOWN, wait 0.15s, 8 MOVE steps, wait 0.4s, UP.
    **A fast swipe only scrolls ~1/3 of the distance** (the game ignores the start of the
    motion). This pattern scrolls 1:1. The scroll wheel does nothing in-game.
  - `screencap()` → `exec-out screencap -p`, falling back to screencap-to-file + `adb pull`
    (BlueStacks sometimes closes the stream with `error: closed`), then reconnect + retry.
- Positions live in `coords.json` under `"adb"`, as fractions (0–1) of the Android screen.
  - `--adb --calibrate [--only a,b]`: shows an adb screenshot (matplotlib), I click the point.
  - `--adb --tune-scroll members|clans`: live swipe tuning (+/-, undo, save).
  - `--demo`, `--members/--clans/--rounds N`, `--no-invite` for quick tests.
- Mouse mode (no `--adb`) still exists (pyautogui + Quartz window lookup) but is legacy.

### Lessons learned the hard way
- **Popups open next to the element you tap.** Always tap the same spot or later
  positions drift (e.g. "Profile" turns into "Visit").
- **Wait for screens to load:** popup ~0.4s, profile page ~1s, back ~0.8s, clan page ~1.5s.
- The in-game clan page opens with member #1 at the very bottom of the screen.
- In-game "Search Clans" returns the same clans in the same order every time, which is
  why we're switching strategies.

## New system to build

```
 1. WATCH (API, runs on a schedule)
    /clans search (filters + cursor paging) → grow a set of watched clans
    poll /clans/{tag}/members for every watched clan
        → upsert every player: tag, name, role, TH, clan, last_seen_in_clan_at
        → a tag that DISAPPEARED from its clan → /players/{tag}
              no clan now   → HOT lead (just left = clanless + active)
              new clan      → just update the record
 2. SCORE
    /players/{tag}: TH, heroes, troops, warStars, donations, attackWins, trophies
    • skip role leader / coLeader (established; API roles: member, admin=Elder, coLeader, leader)
    • not rushed: hero (+troop) levels vs per-TH caps (API only gives global maxLevel,
      so per-TH caps come from a library like coc.py if it has them, or a table)
    • active: diff snapshots (trophies / donations / attackWins changed)
    • likely to move: clanless >> weak/dying clan (few members, no wars, low donations)
    • my preferences (TH range etc.) in a config file
    → ranked invite queue
 3. INVITE (ADB)
    Social tab → Find Friends → tap "Search for Player" (field already shows "#")
    → `adb shell input text <tag without #>` → Search → open profile → Invite → back
    • log every invite (tag, time, result); cooldown before re-inviting (e.g. 14 days)
    • handle "player not found"; use screenshot checks to confirm which screen we're on
 4. LEARN
    poll my clan's members → who joined after an invite → conversion by score bucket
    → tune scoring weights
```

### Data (SQLite)
- `clans`: tag, name, members, war frequency, location, last_polled_at
- `players`: tag, name, current clan tag (NULL = clanless), role, TH, last_seen_in_clan_at,
  last_checked_at, latest snapshot fields
- `snapshots`: player tag, time, trophies, donations, attackWins, warStars (for activity)
- `memberships`: player tag, clan tag, first_seen, last_seen (history of clan moves)
- `invites`: player tag, time, result, score at invite time
- `joins`: player tag, joined_at (from polling my clan)

### Scale
- Watching ~5k clans every ~6h ≈ 20k API calls/day. Respect rate limits (back off on 429).
- Invites go through the UI at roughly 6–10s each (~400–600/hour), so thousands/day means
  long runs. Make the invite loop robust: recover from unexpected screens and resume from
  the queue.

## Check these first
1. **API access:** keys are IP-locked and my IP changes (campus Wi-Fi). Check whether
   RoyaleAPI's CoC proxy (`cocproxy.royaleapi.dev`) still works and which IP to whitelist.
2. **API fields:** confirm what `/clans/{tag}/members` returns (townHallLevel? role?) and
   what's in `/players/{tag}`.
3. **Invite flow:** confirm Find Friends → profile → Invite works, and what the
   "not found" screen looks like.
4. **Invite limits:** does the game cap invites per day, or flag fast repeated invites?
   Measure the real seconds per invite.

## How I'd like to work
Short design first (modules, schema, scoring formula), then build in runnable steps:
API watcher + DB → scoring → ADB invite flow → learning loop. Keep `python.py`'s ADB code
reusable (move it into a module rather than copying it).
