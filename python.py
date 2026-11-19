"""
Clash of Clans Invite Bot — works on macOS and Windows.

Usage (ADB mode: taps go straight into BlueStacks, your mouse stays free):
    python3 python.py --adb --calibrate    # click each button on a screenshot (do this first)
    python3 python.py --adb --demo         # quick test
    python3 python.py --adb                # run the bot (stop with Ctrl+C)

Usage (mouse mode: moves your real mouse):
    python3 python.py --calibrate          # record click positions (do this first on a new machine)
    python3 python.py --calibrate --only invite_text,back_arrow   # redo specific points
    python3 python.py                      # run the bot
    python3 python.py --demo               # quick test: 2 members x 2 clans, then stop
    python3 python.py --members 3 --clans 4 --rounds 1 --no-invite   # custom test, no invites sent
    python3 python.py --list-windows       # macOS: show window/app names if the game isn't found

    python3 python.py --window "Clash of Clans"   # control a different app/emulator

Stop the bot: press Esc, or slam the mouse into the top-left corner of the screen.
"""

import argparse
import glob
import io
import json
import os
import platform
import random
import shutil
import struct
import subprocess
import sys
import time

import pyautogui

IS_MAC = platform.system() == "Darwin"
PLATFORM_KEY = "mac" if IS_MAC else "windows"

# Substring of the app name (macOS) or window title (Windows) to look for.
# Matches "BlueStacks", "BlueStacks Air", "BlueStacks App Player", etc. Override with --window.
WINDOW_NAME = "BlueStacks"

COORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coords.json")

# Moving the mouse to the top-left corner aborts the script (backup kill switch).
pyautogui.FAILSAFE = True

# Every click target, in the order you'll naturally reach them in-game during calibration.
POINTS = [
    ("player_profile", "Your profile button (top-left of the home village). Then click it."),
    ("join_clan_text", "The 'Join Clan' tab. Then click it."),
    ("first_clan", "The FIRST (left) clan card in the clan list."),
    ("second_clan", "The SECOND (right) clan card in the clan list."),
    ("scroll_distance_clan", "Where a clan-list scroll drag should END (it starts on the first clan card)."),
    ("refresh_button", "The refresh button for the clan list. Then click the first clan."),
    ("view_clan", "The 'View Clan' button. Then click it."),
    ("first_member", "The first member row in the member list."),
    ("scroll_distance_members", "Where a member-list scroll drag should END (it starts on the first member)."),
    ("member_profile", "Click the first member, then hover the 'Profile' button in the popup. Then click it."),
    ("invite_text", "The 'Invite' button on the player's profile."),
    ("back_arrow", "The back arrow (top-left)."),
]

# The original coordinates, measured on Windows.
DEFAULT_COORDS = {
    "windows": {
        "player_profile": [0.032, 0.089],
        "join_clan_text": [0.586, 0.125],
        "first_clan": [0.308, 0.540],
        "view_clan": [0.424, 0.800],
        "first_member": [0.424, 0.889],
        "member_profile": [0.609, 0.807],
        "invite_text": [0.365, 0.544],
        "back_arrow": [0.143, 0.131],
        "scroll_distance_members": [0.424, 0.790],
        "second_clan": [0.688, 0.540],
        "scroll_distance_clan": [0.308, 0.256],
        "refresh_button": [0.506, 0.866],
    }
}


# --------------------------------------------------------------------------- window handling

class Window:
    def __init__(self, left, top, width, height, pid=None, handle=None):
        self.left, self.top, self.width, self.height = left, top, width, height
        self.pid = pid
        self.handle = handle

    def __repr__(self):
        return f"Window(left={self.left}, top={self.top}, {self.width}x{self.height})"


def _mac_window_infos():
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGNullWindowID,
        kCGWindowListExcludeDesktopElements,
        kCGWindowListOptionOnScreenOnly,
    )
    return CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, kCGNullWindowID
    ) or []


def _find_window_mac(name):
    name = name.lower()
    best = None
    for info in _mac_window_infos():
        if info.get("kCGWindowLayer", 0) != 0:  # skip menu bar, overlays, etc.
            continue
        owner = str(info.get("kCGWindowOwnerName", "") or "")
        title = str(info.get("kCGWindowName", "") or "")
        if name not in owner.lower() and name not in title.lower():
            continue
        b = info["kCGWindowBounds"]
        cand = Window(int(b["X"]), int(b["Y"]), int(b["Width"]), int(b["Height"]),
                      pid=int(info["kCGWindowOwnerPID"]))
        # The app may own several windows; the biggest one is the game.
        if best is None or cand.width * cand.height > best.width * best.height:
            best = cand
    return best


def _find_window_windows(name):
    import pygetwindow as gw
    matches = gw.getWindowsWithTitle(name)
    if not matches:
        return None
    w = matches[0]
    if w.isMinimized:
        w.restore()
    return Window(w.left, w.top, w.width, w.height, handle=w)


def find_window():
    return _find_window_mac(WINDOW_NAME) if IS_MAC else _find_window_windows(WINDOW_NAME)


def activate(win):
    if IS_MAC:
        try:
            from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(win.pid)
            if app is not None:
                app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                return
        except Exception:
            pass
        subprocess.run(["osascript", "-e", f'tell application "{WINDOW_NAME}" to activate'],
                       capture_output=True)
    else:
        try:
            win.handle.activate()
        except Exception:
            pass


def get_window():
    win = find_window()
    if win is None and IS_MAC:
        # The game may be minimized or hidden; try bringing it forward, then look again.
        subprocess.run(["osascript", "-e", f'tell application "{WINDOW_NAME}" to activate'],
                       capture_output=True)
        time.sleep(1.5)
        win = find_window()
    if win is None:
        print(f"Couldn't find a window matching '{WINDOW_NAME}'. Is BlueStacks open (and not minimized)?")
        if IS_MAC:
            print("Run `python3 python.py --list-windows` to see the names macOS reports.")
        sys.exit(1)
    return win


def list_windows():
    if not IS_MAC:
        import pygetwindow as gw
        for t in gw.getAllTitles():
            if t.strip():
                print(t)
        return
    for info in _mac_window_infos():
        if info.get("kCGWindowLayer", 0) != 0:
            continue
        b = info["kCGWindowBounds"]
        print(f"{info.get('kCGWindowOwnerName', '')!r:40} title={info.get('kCGWindowName', '')!r:30} "
              f"{int(b['Width'])}x{int(b['Height'])}")


# --------------------------------------------------------------------------- ADB backend

def find_adb():
    exe = shutil.which("adb")
    if exe:
        return exe
    patterns = [
        "/opt/homebrew/bin/adb",
        "/Applications/BlueStacks*.app/Contents/MacOS/*adb*",
        "/Applications/BlueStacks*.app/Contents/**/*adb",
        r"C:\Program Files\BlueStacks*\HD-Adb.exe",
    ]
    for pat in patterns:
        for path in glob.glob(pat, recursive=True):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    print("Couldn't find adb. Install it with:  brew install android-platform-tools")
    sys.exit(1)


class Adb:
    """Sends taps/swipes straight into the Android system inside BlueStacks: no mouse involved."""

    def __init__(self, serial):
        self.exe = find_adb()
        self.serial = serial
        if serial and ":" in serial:
            subprocess.run([self.exe, "connect", serial], capture_output=True, text=True, timeout=15)
        state = self._run("get-state", check=False).strip()
        if state != "device":
            print(f"Can't reach BlueStacks over ADB at {serial} (adb says: {state or 'nothing'}).")
            print("In BlueStacks: Settings -> Advanced -> turn on 'Android Debug Bridge (ADB)'.")
            print("If it shows a different address than 127.0.0.1:5555, pass it with --adb-serial.")
            sys.exit(1)
        self.width, self.height = self.screen_size()
        # Android 10+ has `input motionevent`, which lets us do a proper press-hold-move swipe.
        self.has_motionevent = "motionevent" in self.shell("input", check=False)

    def _cmd(self, *args):
        return [self.exe] + (["-s", self.serial] if self.serial else []) + list(args)

    def _run(self, *args, check=True):
        r = subprocess.run(self._cmd(*args), capture_output=True, text=True, timeout=60)
        if check and r.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
        return r.stdout + r.stderr

    def shell(self, command, check=True):
        return self._run("shell", command, check=check)

    def screencap(self):
        r = subprocess.run(self._cmd("exec-out", "screencap", "-p"), capture_output=True, timeout=30)
        if not r.stdout.startswith(b"\x89PNG"):
            raise RuntimeError("adb screencap didn't return a PNG: " + r.stderr.decode(errors="replace"))
        return r.stdout

    def screen_size(self):
        png = self.screencap()
        return struct.unpack(">II", png[16:24])  # width, height from the PNG header

    def to_px(self, rel, jitter=0):
        x = round(rel[0] * self.width) + random.randint(-jitter, jitter)
        y = round(rel[1] * self.height) + random.randint(-jitter, jitter)
        return min(max(x, 0), self.width - 1), min(max(y, 0), self.height - 1)

    def tap(self, rel):
        x, y = self.to_px(rel, jitter=5)
        self.shell(f"input tap {x} {y}")

    def swipe(self, start, end, extra=0.0, steps=8):
        """Same press, hold, move in steps, pause, release pattern the game needs (see drag())."""
        sx, sy = self.to_px(start)
        ex, ey = self.to_px(end)
        if self.has_motionevent:
            cmds = [f"input motionevent DOWN {sx} {sy}", "sleep 0.15"]
            for i in range(1, steps + 1):
                t = i / steps
                cmds.append(f"input motionevent MOVE {round(sx + (ex - sx) * t)} {round(sy + (ey - sy) * t)}")
            cmds += ["sleep 0.4", f"input motionevent UP {ex} {ey}"]
            self.shell("; ".join(cmds))  # one round trip
        else:
            # Older Android: a slow swipe keeps the end velocity low so the list barely flings.
            self.shell(f"input swipe {sx} {sy} {ex} {ey} {int((0.9 + extra) * 1000)}")


ADB = None  # set by --adb


# --------------------------------------------------------------------------- coordinates

def load_all_coords():
    data = json.loads(json.dumps(DEFAULT_COORDS))  # deep copy
    if os.path.exists(COORDS_FILE):
        with open(COORDS_FILE) as f:
            for plat, pts in json.load(f).items():
                data.setdefault(plat, {}).update(pts)
    return data


def save_all_coords(data):
    with open(COORDS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def coords_key():
    return "adb" if ADB else PLATFORM_KEY


def load_coords():
    coords = load_all_coords().get(coords_key(), {})
    missing = [k for k, _ in POINTS if k not in coords]
    if missing:
        print(f"No calibrated positions for {coords_key()} yet: {', '.join(missing)}")
        print(f"Run `python3 python.py {'--adb ' if ADB else ''}--calibrate` first.")
        sys.exit(1)
    return {k: tuple(v) for k, v in coords.items()}


# --------------------------------------------------------------------------- mouse helpers

win = None
C = {}


def relative_to_absolute(coordinates):
    rel_x, rel_y = coordinates
    return int(win.left + rel_x * win.width), int(win.top + rel_y * win.height)


def random_sleep_float():
    return random.uniform(0.30, 0.40)


def move_mouse(coordinates, do_click):
    if ADB:
        if do_click:
            ADB.tap(coordinates)
        time.sleep(random.uniform(0.1, 0.5))
        return
    x, y = relative_to_absolute(coordinates)
    pyautogui.moveTo(x + random.randint(-5, 5), y + random.randint(-5, 5))
    if do_click:
        pyautogui.leftClick()
    time.sleep(random.uniform(0.1, 0.5))


def drag(start, end, extra=0.0, steps=12):
    """Touch-style swipe from `start` to `end` that the game scrolls 1:1.

    Tested in BlueStacks Air: a fast press-and-move only scrolls ~1/3 of the distance,
    because the game swallows the start of the motion as touch "slop". What works:
    press, hold briefly, move in many small steps, pause (kills the fling), release.

    dragTo (not moveTo) is required on macOS so the moves are sent as 'mouse dragged'
    events, and button must be "left" explicitly (pyautogui's default "primary" crashes there).
    """
    if ADB:
        ADB.swipe(start, end, extra)
        return
    sx, sy = relative_to_absolute(start)
    ex, ey = relative_to_absolute(end)
    pyautogui.moveTo(sx, sy)
    pyautogui.mouseDown(button="left")
    time.sleep(0.15)  # let the game register the touch before moving

    step_delay = (random_sleep_float() + extra) / steps
    for i in range(1, steps + 1):
        t = i / steps
        pyautogui.dragTo(round(sx + (ex - sx) * t), round(sy + (ey - sy) * t),
                         button="left", mouseDownUp=False, _pause=False)
        time.sleep(step_delay)

    time.sleep(0.4)  # hold still so the list stops instead of flinging
    pyautogui.mouseUp(button="left")


# --------------------------------------------------------------------------- kill switch

def start_kill_switch():
    try:
        from pynput import keyboard
    except ImportError:
        print("pynput not installed — Esc won't work. Use the corner failsafe instead.")
        return

    def on_press(key):
        if key == keyboard.Key.esc:
            print("Kill switch activated. Exiting...")
            os._exit(0)

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()


# --------------------------------------------------------------------------- modes

def calibrate_adb(only=None):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Calibration in ADB mode needs matplotlib:  pip install matplotlib")
        sys.exit(1)

    data = load_all_coords()
    plat = data.setdefault("adb", {})
    points = [(k, d) for k, d in POINTS if not only or k in only]
    print(f"Calibrating {len(points)} point(s) over ADB. BlueStacks screen: {ADB.width}x{ADB.height}")
    print("For each one: get the game to the right screen in BlueStacks (do any clicks the step")
    print("mentions there yourself), press Enter here, then click the spot on the screenshot.\n")

    for key, desc in points:
        print(f"[{key}] {desc}")
        input("   Press Enter to grab a screenshot... ")
        img = plt.imread(io.BytesIO(ADB.screencap()), format="png")
        fig, ax = plt.subplots(figsize=(12, 12 * ADB.height / ADB.width))
        ax.imshow(img)
        ax.set_title(f"Click: {key}  ({desc})", fontsize=9)
        ax.axis("off")
        fig.tight_layout()
        picked = plt.ginput(1, timeout=0)
        plt.close(fig)
        if not picked:
            print("   skipped (no click)")
            continue
        x, y = picked[0]
        rel = [round(x / ADB.width, 3), round(y / ADB.height, 3)]
        plat[key] = rel
        save_all_coords(data)
        print(f"   captured {key} = {rel}")

    print(f"\nSaved to {COORDS_FILE}")


def calibrate(only=None, delay=4):
    if ADB:
        return calibrate_adb(only)
    global win
    win = get_window()
    activate(win)
    data = load_all_coords()
    plat = data.setdefault(PLATFORM_KEY, {})

    points = [(k, d) for k, d in POINTS if not only or k in only]
    print(f"Calibrating {len(points)} point(s) for {PLATFORM_KEY}. Window: {win}")
    print(f"For each one: hover the mouse over it in the game. Position is captured after {delay}s.")
    print("You can click around in the game during the countdown to reach the right screen.\n")

    for key, desc in points:
        print(f"[{key}] {desc}")
        for s in range(delay, 0, -1):
            print(f"   capturing in {s}...", end="\r", flush=True)
            time.sleep(1)
        win = get_window()  # in case the window moved
        mx, my = pyautogui.position()
        rel = [round((mx - win.left) / win.width, 3), round((my - win.top) / win.height, 3)]
        plat[key] = rel
        flag = "" if 0 <= rel[0] <= 1 and 0 <= rel[1] <= 1 else "   ⚠️ outside the game window!"
        print(f"   captured {key} = {rel}{flag}      ")
        save_all_coords(data)

    print(f"\nSaved to {COORDS_FILE}")


def run(members=10, clans=10, rounds=None, invite=True):
    """members: per clan; clans: per round (scrolls the clan list after every 2);
    rounds: list refreshes before stopping (None = forever); invite=False skips the Invite click."""
    global win, C
    C = load_coords()
    if ADB:
        print(f"Controlling BlueStacks over ADB ({ADB.serial}, {ADB.width}x{ADB.height}). "
              "Your mouse is free. BlueStacks can be behind other windows.")
        print("Stop with Ctrl+C in this Terminal.")
    else:
        win = get_window()
        activate(win)
        start_kill_switch()
        print(f"Controlling window: {win}")
    print(f"Plan: {members} member(s) x {clans} clan(s) per round, "
          f"{'forever' if rounds is None else f'{rounds} round(s)'}"
          f"{'' if invite else ', NOT clicking Invite'}.")
    print("Get Clash of Clans on the home village screen. Starting in 5 seconds"
          + ("." if ADB else " (Esc or mouse to top-left corner to stop)."))
    time.sleep(5)

    move_mouse(C["player_profile"], True)
    time.sleep(1)
    move_mouse(C["join_clan_text"], True)
    time.sleep(1)

    round_num = 0
    while rounds is None or round_num < rounds:
        round_num += 1
        if not ADB:
            win = get_window()  # pick up any window move/resize between rounds

        for counter in range(clans):
            side = "right" if counter % 2 else "left"
            print(f"[round {round_num}] clan {counter + 1}/{clans} ({side})")
            clan = C["second_clan"] if counter % 2 else C["first_clan"]
            move_mouse(clan, True)
            move_mouse(C["view_clan"], True)
            time.sleep(1)

            for m in range(members):
                print(f"    member {m + 1}/{members}")
                move_mouse(C["first_member"], True)
                move_mouse(C["member_profile"], True)
                time.sleep(0.1)
                if invite:
                    move_mouse(C["invite_text"], True)
                move_mouse(C["back_arrow"], True)
                drag(C["first_member"], C["scroll_distance_members"])

            move_mouse(C["back_arrow"], True)

            if counter % 2:
                print("    scrolling clan list")
                drag(C["first_clan"], C["scroll_distance_clan"], extra=0.1)

        if rounds is None or round_num < rounds:
            move_mouse(C["refresh_button"], True)
            time.sleep(1)

    print("Done.")


def main():
    global WINDOW_NAME
    p = argparse.ArgumentParser(description="Clash of Clans invite bot")
    p.add_argument("--calibrate", action="store_true", help="record click positions for this machine")
    p.add_argument("--only", help="comma-separated point names to recalibrate")
    p.add_argument("--delay", type=int, default=4, help="seconds per point while calibrating")
    p.add_argument("--list-windows", action="store_true", help="print visible window names")
    p.add_argument("--window", help=f"app/window name to control (default: {WINDOW_NAME})")
    p.add_argument("--adb", action="store_true",
                   help="control BlueStacks over ADB instead of the mouse (mouse stays free)")
    p.add_argument("--adb-serial", default="127.0.0.1:5555",
                   help="ADB address shown in BlueStacks' ADB setting (default 127.0.0.1:5555)")
    p.add_argument("--demo", action="store_true",
                   help="quick test: 2 members x 2 clans, 1 round (includes one clan-list scroll)")
    p.add_argument("--members", type=int, help="members to invite per clan (default 10)")
    p.add_argument("--clans", type=int, help="clans per round (default 10)")
    p.add_argument("--rounds", type=int, help="rounds before stopping (default: forever)")
    p.add_argument("--no-invite", action="store_true", help="go through the motions without clicking Invite")
    args = p.parse_args()

    if args.window:
        WINDOW_NAME = args.window

    global ADB
    try:
        if args.adb and not args.list_windows:
            ADB = Adb(args.adb_serial)
        if args.list_windows:
            list_windows()
        elif args.calibrate:
            only = set(args.only.split(",")) if args.only else None
            calibrate(only, args.delay)
        else:
            members, clans, rounds = (2, 2, 1) if args.demo else (10, 10, None)
            run(members=args.members or members,
                clans=args.clans or clans,
                rounds=args.rounds or rounds,
                invite=not args.no_invite)
    except pyautogui.FailSafeException:
        print("Failsafe triggered (mouse in corner). Exiting.")
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
