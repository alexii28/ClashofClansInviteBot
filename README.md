# ClashofClansInviteBot (WIP)
Invite users to your clan automatically. Runs on macOS and Windows.

## Setup (macOS)
1. Install **BlueStacks** (BlueStacks Air on Apple Silicon Macs), install Clash of Clans inside it, and open the game.
2. In Terminal, from this folder:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Give your terminal app (Terminal, iTerm, or VS Code) these permissions in **System Settings → Privacy & Security**:
   - **Accessibility**: lets the bot move and click the mouse
   - **Input Monitoring**: lets Esc stop the bot

   Quit and reopen the terminal after granting them.

## Calibrate (once per machine)
Button positions are saved as fractions of the BlueStacks window, but they're different on every machine, so record them first:
```bash
python3 python.py --calibrate
```
For each prompt, hover over the named button in the game. The position is captured after 4 seconds, and you can click through the game during the countdown to get to the next screen. Positions are saved to `coords.json`.

**Keep the BlueStacks window the same size after calibrating.** BlueStacks' toolbar doesn't resize with the game area, so a different window size moves the buttons a little. Moving the window is fine.

To redo specific points: `python3 python.py --calibrate --only invite_text,back_arrow`

## Run
```bash
python3 python.py
```
Start from the home village screen.

**Quick test:** `python3 python.py --demo` invites 2 members in each of 2 clans (with one clan-list scroll), then stops.
Customize with `--members N`, `--clans N` and `--rounds N`. Add `--no-invite` to test clicks and scrolling without sending invites. To stop: press **Esc**, or move the mouse into the **top-left corner** of the screen.

The bot looks for a window named "BlueStacks". If it doesn't find it, run `python3 python.py --list-windows` and pass the name it shows: `python3 python.py --window "Name Here"` (on the `--calibrate` run too).

> Supercell's ToS prohibits third-party automation, so use an alt account.
