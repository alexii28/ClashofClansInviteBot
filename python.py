import pygetwindow as gw
import pyautogui
import time
import keyboard
import threading
import os
import random

# Configuration
TARGET_WINDOW_TITLE = "Clash of Clans - 0jOrangeJuice"  # Example
relative_x = 0.5   # 50% from the left
relative_y = 0.25  # 25% from the top
debug_mode = False

# Get the window
try:
    window = gw.getWindowsWithTitle(TARGET_WINDOW_TITLE)[0]
except IndexError:
    print(f"Window with title '{TARGET_WINDOW_TITLE}' not found.")
    exit()

# Make sure the window is not minimized or off-screen
if window.isMinimized:
    window.restore()

# Bring the window to the front
window.activate()

# Get window dimensions
left, top = window.left, window.top
width, height = window.width, window.height

# Calculate center
center_x = left + width // 2
center_y = top + height // 2

# Square dimensions (smaller than window)
side_length = min(width, height) // 3

start_x = center_x - side_length // 2
start_y = center_y - side_length // 2

print(f"Controlling window: {TARGET_WINDOW_TITLE}")

abs_x = int(window.left + relative_x * window.width)
abs_y = int(window.top + relative_y * window.height)

# Coordinate Configurations
player_profile = (0.040, 0.100)
join_clan_text = (0.586, 0.125)

time.sleep(1) # give time for clans to load
first_clan = (0.308, 0.540)
view_clan = (0.424, 0.800)
first_member = (0.424, 0.889)
member_profile = (0.609, 0.807)
invite_text = (0.365, 0.544)
back_arrow = (0.143, 0.131)

scroll_distance_members = (0.424, 0.790)

second_clan = (0.688, 0.540)
scroll_distance_clan = (0.308, 0.190)

refresh_button = (0.506, 0.866)


def relative_to_absolute(coordinates):
    """
    Convert relative coordinates (0 to 1) within a window to absolute screen coordinates.

    Args:
        window_title (str): The exact or partial title of the target window.
        rel_x (float): Relative horizontal coordinate (0.0 to 1.0).
        rel_y (float): Relative vertical coordinate (0.0 to 1.0).

    Returns:
        (int, int): Tuple of absolute (x, y) screen coordinates.
    """

    rel_x, rel_y = coordinates
    abs_x = int(window.left + rel_x * window.width)
    abs_y = int(window.top + rel_y * window.height)

    return abs_x, abs_y

def moveMouse(coordinates, doClick):
    x, y = relative_to_absolute(coordinates)
    pyautogui.moveTo(x + random.randint(-5, 5), y + (random.randint(-5, 5)))
    if doClick:
        pyautogui.leftClick()
    time.sleep(random.uniform(.05, .1))
    return

def randomSleepFloat():
    return random.uniform(.10, .2)


# Global flag
running = True

def kill_switch_listener():
    global running
    keyboard.wait('esc')  # blocks until Esc is pressed
    print("Kill switch activated. Exiting...")
    running = False

    #Force close script 
    os._exit(0)

# Start kill switch thread
threading.Thread(target=kill_switch_listener, daemon=True).start()


#Give user time to setup
print("Please enter Clash of Clans on the home village screen. You have 5 seconds")
time.sleep(5)

#Loop main program
if not debug_mode:
    #setup
    moveMouse(player_profile, True)
    moveMouse(join_clan_text, True)
    while running:
        

        #start clan loop
        for counter in range(10):
            if counter % 2:
                clan_coordinates = second_clan
            else:
                clan_coordinates = first_clan

            moveMouse(clan_coordinates, True)
            moveMouse(view_clan, True)


            #start player loop
            for i in range(10):
                moveMouse(first_member, True)
                moveMouse(member_profile, True)
                moveMouse(invite_text, True)
                moveMouse(back_arrow, True)

                moveMouse(first_member, False)
                x, y = relative_to_absolute(scroll_distance_members)
                pyautogui.mouseDown()
                pyautogui.moveTo(x, y, duration=randomSleepFloat())
                time.sleep(randomSleepFloat())
                pyautogui.mouseUp()
            #end player loop
            moveMouse(back_arrow, True)

            if counter % 2:
                moveMouse(first_clan, False)
                x, y = relative_to_absolute(scroll_distance_clan)
                pyautogui.mouseDown()
                pyautogui.moveTo(x, y, duration=randomSleepFloat() + 0.1)
                time.sleep(randomSleepFloat())
                pyautogui.mouseUp()

        moveMouse(refresh_button, True)

        time.sleep(1)

# Find Relative Coordinates
if debug_mode and running:
    print("Hover over the target point inside the window")

    # Get mouse position
    mouse_x, mouse_y = pyautogui.position()

    # Get window info
    left, top, width, height = window.left, window.top, window.width, window.height

    # Calculate relative units
    relative_x = (mouse_x - left) / width
    relative_y = (mouse_y - top) / height

    print(f"\nMouse absolute position: ({mouse_x}, {mouse_y})")
    print(f"Window top-left: ({left}, {top}), size: {width}x{height}")
    print(f" Relative coordinates: x, y = {relative_x:.3f}, {relative_y:.3f}")