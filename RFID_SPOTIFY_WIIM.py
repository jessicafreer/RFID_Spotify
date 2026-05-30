import argparse
import json
import os
import re
import sys
import time
import select
import termios
import tty

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from spotipy.cache_handler import CacheFileHandler
except ImportError:
    print("Please install Spotipy first: pip install spotipy")
    sys.exit(1)


CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "spotify": {
        "client_id": "PASTE_YOUR_SPOTIFY_CLIENT_ID_HERE",
        "client_secret": "PASTE_YOUR_SPOTIFY_CLIENT_SECRET_HERE",
        "redirect_uri": "http://127.0.0.1:8888/callback",
        "scope": "user-read-playback-state user-modify-playback-state",
        "cache_path": ".spotify_rfid_cache"
    },
    "wiim": {
        "device_name": "WiiM",
        "match_mode": "contains",
        "initial_volume": 50
    },
    "rfid": {
        "mapping_file": "rfid_spotify_map.json"
    }
}


def deep_merge(defaults, existing):
    """Keep existing config values, but add any new defaults that are missing."""
    result = dict(defaults)

    for key, value in existing.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_config():
    """Load config.json, creating or upgrading it if needed."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)

        print(f"Created {CONFIG_FILE}. Add your Spotify credentials and WIIM device name, then run again.")
        sys.exit(0)

    with open(CONFIG_FILE, "r") as f:
        existing_config = json.load(f)

    config = deep_merge(DEFAULT_CONFIG, existing_config)

    # Save back so old Bluetooth/Raspotify-era config files get the new WIIM section.
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

    return config


def load_mapping(mapping_file):
    """Load RFID card ID to Spotify playlist mapping."""
    if os.path.exists(mapping_file):
        with open(mapping_file, "r") as f:
            return json.load(f)

    print(f"Mapping file not found: {mapping_file}")
    print("Create it with entries like:")
    print('{')
    print('  "1234567890": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"')
    print('}')
    return {}


def create_spotify_client(config):
    spotify_config = config["spotify"]

    missing = [
        key for key in ["client_id", "client_secret", "redirect_uri"]
        if not spotify_config.get(key) or spotify_config[key].startswith("PASTE_")
    ]

    if missing:
        print(f"Missing Spotify config values in {CONFIG_FILE}: {', '.join(missing)}")
        sys.exit(1)

    auth_manager = SpotifyOAuth(
        client_id=spotify_config["client_id"],
        client_secret=spotify_config["client_secret"],
        redirect_uri=spotify_config["redirect_uri"],
        scope=spotify_config["scope"],
        cache_handler=CacheFileHandler(
            cache_path=spotify_config.get("cache_path", ".spotify_rfid_cache")
        )
    )

    return spotipy.Spotify(auth_manager=auth_manager)


def normalize_playlist_context(value):
    """
    Accepts:
      - bare playlist ID
      - spotify:playlist:<id>
      - https://open.spotify.com/playlist/<id>?si=...
    Returns:
      - spotify:playlist:<id>
    """
    value = value.strip()

    if value.startswith("spotify:playlist:"):
        return value

    match = re.search(r"open\.spotify\.com/playlist/([A-Za-z0-9]+)", value)
    if match:
        return f"spotify:playlist:{match.group(1)}"

    return f"spotify:playlist:{value}"


def list_spotify_devices(sp):
    """Print available Spotify Connect devices."""
    devices_response = sp.devices()
    devices = devices_response.get("devices", [])

    if not devices:
        print("No Spotify Connect devices found.")
        return []

    print("Available Spotify Connect devices:")
    for device in devices:
        print(
            f"  - {device.get('name')} "
            f"({device.get('type')}) "
            f"active={device.get('is_active')} "
            f"restricted={device.get('is_restricted')}"
        )

    return devices


def find_wiim_device(sp, config, max_retries=6):
    """
    Find the WIIM by Spotify Connect device name.

    If Spotify does not show the WIIM, open Spotify on your phone/computer,
    start any song, and select the WIIM from the Spotify device picker once.
    """
    wiim_config = config["wiim"]
    target_name = wiim_config["device_name"].strip().lower()
    match_mode = wiim_config.get("match_mode", "contains").strip().lower()

    for attempt in range(max_retries):
        devices = sp.devices().get("devices", [])

        for device in devices:
            device_name = device.get("name", "")
            device_name_lower = device_name.lower()

            if match_mode == "exact":
                matched = device_name_lower == target_name
            else:
                matched = target_name in device_name_lower

            if matched:
                if device.get("is_restricted"):
                    print(f"Found WIIM device '{device_name}', but Spotify says it is restricted.")
                    return None

                print(f"Found WIIM Spotify Connect device: {device_name}")
                return device

        if attempt < max_retries - 1:
            print(f"WIIM device not found yet. Retrying... ({attempt + 1}/{max_retries})")
            time.sleep(2)

    print("Could not find the WIIM in Spotify Connect devices.")
    list_spotify_devices(sp)
    return None


def set_volume_if_configured(sp, device_id, config):
    volume = config["wiim"].get("initial_volume")

    if volume is None:
        return

    try:
        volume = int(volume)
        volume = max(0, min(100, volume))
        sp.volume(volume, device_id=device_id)
        print(f"Set WIIM volume to {volume}")
    except Exception as e:
        print(f"Could not set volume. Continuing anyway. Details: {e}")


def play_spotify_playlist_on_wiim(playlist_value, sp, config):
    """Start playlist playback on WIIM via Spotify Connect."""
    device = find_wiim_device(sp, config)

    if not device:
        print("Playback failed because the WIIM was not available as a Spotify Connect device.")
        return False

    playlist_context_uri = normalize_playlist_context(playlist_value)
    device_id = device["id"]

    try:
        set_volume_if_configured(sp, device_id, config)

        sp.start_playback(
            device_id=device_id,
            context_uri=playlist_context_uri
        )

        print(f"Playing {playlist_context_uri} on {device['name']} over Wi-Fi")
        return True

    except Exception as e:
        print(f"Error starting playback on WIIM: {e}")
        return False


def read_rfid_card():
    """Read RFID card ID from a USB keyboard-wedge RFID reader."""
    card_id = ""
    print("Scan an RFID card...")

    old_settings = termios.tcgetattr(sys.stdin)

    try:
        tty.setraw(sys.stdin.fileno())

        while True:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                char = sys.stdin.read(1)

                if char in ["\r", "\n"]:
                    if card_id:
                        print(f"\nCard ID: {card_id}")
                        return card_id

                elif char.isdigit():
                    card_id += char
                    sys.stdout.write(char)
                    sys.stdout.flush()

                elif char == "\x03":
                    raise KeyboardInterrupt

                elif not char.isspace():
                    card_id = ""
                    print(f"\nIgnoring invalid character: {repr(char)}")
                    print("Scan an RFID card...")

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def main():
    parser = argparse.ArgumentParser(description="RFID Spotify playlist player for WIIM over Wi-Fi")
    parser.add_argument("--list-devices", action="store_true", help="List available Spotify Connect devices")
    parser.add_argument("--test-playlist", help="Test playing a playlist ID, URI, or Spotify playlist URL")
    args = parser.parse_args()

    config = load_config()
    mapping_file = config["rfid"]["mapping_file"]

    sp = create_spotify_client(config)

    print("\n--- Spotify RFID Player for WIIM ---\n")

    if args.list_devices:
        list_spotify_devices(sp)
        return

    if args.test_playlist:
        play_spotify_playlist_on_wiim(args.test_playlist, sp, config)
        return

    mapping = load_mapping(mapping_file)

    if not mapping:
        print("No RFID-to-playlist mappings loaded.")
        return

    print(f"Mapping file: {mapping_file}")
    print(f"Target WIIM device name: {config['wiim']['device_name']}")
    print("Ready.\n")

    try:
        while True:
            card_id = read_rfid_card()

            playlist_value = mapping.get(card_id)

            if playlist_value:
                print(f"Found playlist for card {card_id}")
                success = play_spotify_playlist_on_wiim(playlist_value, sp, config)

                if success:
                    print("Playback started successfully.")
                else:
                    print("Failed to start playback.")

                print("\nReady for next card...\n")

            else:
                print(f"No playlist found for card {card_id}.")
                print("Ready for next card...\n")

    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()