"""
Clash of Clans Invite Bot — works on macOS and Windows.

Usage:
    python3 python.py --calibrate          # record click positions (do this first on a new machine)
    python3 python.py --calibrate --only invite_text,back_arrow   # redo specific points
    python3 python.py                      # run the bot
    python3 python.py --list-windows       # macOS: show window/app names if the game isn't found

    python3 python.py --window "Clash of Clans"   # control a different app/emulator

Stop the bot: press Esc, or slam the mouse into the top-left corner of the screen.
"""

import argparse
import json
import os
import platform
import random
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


def load_coords():
    coords = load_all_coords().get(PLATFORM_KEY, {})
    missing = [k for k, _ in POINTS if k not in coords]
    if missing:
        print(f"No calibrated positions for {PLATFORM_KEY} yet: {', '.join(missing)}")
        print("Run `python3 python.py --calibrate` first.")
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
    x, y = relative_to_absolute(coordinates)
    pyautogui.moveTo(x + random.randint(-5, 5), y + random.randint(-5, 5))
    if do_click:
        pyautogui.leftClick()
    time.sleep(random.uniform(0.1, 0.5))


def drag(start, end, extra=0.0):
    """Press at `start`, drag to `end`, pause, release (pause stops the scroll from flinging).

    dragTo is required on macOS: a plain moveTo while the button is held sends
    'mouse moved' instead of 'mouse dragged' events, so nothing would scroll.
    """
    move_mouse(start, False)
    x, y = relative_to_absolute(end)
    pyautogui.mouseDown(button="left")
    # button must be "left" explicitly: dragTo's default "primary" crashes on macOS (pyautogui bug)
    pyautogui.dragTo(x, y, duration=random_sleep_float() + extra, button="left", mouseDownUp=False)
    time.sleep(random_sleep_float())
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

def calibrate(only=None, delay=4):
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


def run():
    global win, C
    C = load_coords()
    win = get_window()
    activate(win)
    start_kill_switch()

    print(f"Controlling window: {win}")
    print("Get Clash of Clans on the home village screen. Starting in 5 seconds "
          "(Esc or mouse to top-left corner to stop).")
    time.sleep(5)

    move_mouse(C["player_profile"], True)
    time.sleep(1)
    move_mouse(C["join_clan_text"], True)
    time.sleep(1)

    while True:
        win = get_window()  # pick up any window move/resize between rounds

        for counter in range(10):
            clan = C["second_clan"] if counter % 2 else C["first_clan"]
            move_mouse(clan, True)
            move_mouse(C["view_clan"], True)
            time.sleep(1)

            for _ in range(10):
                move_mouse(C["first_member"], True)
                move_mouse(C["member_profile"], True)
                time.sleep(0.1)
                move_mouse(C["invite_text"], True)
                move_mouse(C["back_arrow"], True)
                drag(C["first_member"], C["scroll_distance_members"])

            move_mouse(C["back_arrow"], True)

            if counter % 2:
                drag(C["first_clan"], C["scroll_distance_clan"], extra=0.1)

        move_mouse(C["refresh_button"], True)
        time.sleep(1)


def main():
    global WINDOW_NAME
    p = argparse.ArgumentParser(description="Clash of Clans invite bot")
    p.add_argument("--calibrate", action="store_true", help="record click positions for this machine")
    p.add_argument("--only", help="comma-separated point names to recalibrate")
    p.add_argument("--delay", type=int, default=4, help="seconds per point while calibrating")
    p.add_argument("--list-windows", action="store_true", help="print visible window names")
    p.add_argument("--window", help=f"app/window name to control (default: {WINDOW_NAME})")
    args = p.parse_args()

    if args.window:
        WINDOW_NAME = args.window

    try:
        if args.list_windows:
            list_windows()
        elif args.calibrate:
            only = set(args.only.split(",")) if args.only else None
            calibrate(only, args.delay)
        else:
            run()
    except pyautogui.FailSafeException:
        print("Failsafe triggered (mouse in corner). Exiting.")


if __name__ == "__main__":
    main()
