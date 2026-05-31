# RFID_Spotify

Play a Spotify playlist on a WiiM device when an RFID card is scanned.

The script reads a USB RFID reader exposed as a Linux input device, looks up the scanned card ID in a JSON mapping file, then starts the mapped playlist through Spotify Connect on your WiiM.

## Requirements

- Spotify Premium
- A Spotify app registration with a client ID and client secret
- A WiiM device visible in Spotify Connect
- A USB RFID reader that appears under `/dev/input/...`
- Linux or Raspberry Pi OS with Python installed
- Programmable RFID cards

## Parts List

Here are the exact products I used. You do not need to use the same hardware, but this is a complete shopping list if you are starting from scratch.

Disclosure: The links below are Amazon affiliate links. As an Amazon Associate I earn from qualifying purchases.

- [Element14 Raspberry Pi 3 B+ Motherboard](https://amzn.to/4ecO3TP) (affiliate link)
- [CanaKit 5V 2.5A Raspberry Pi 3 B+ Power Supply/Adapter](https://amzn.to/43Dsc1P) (affiliate link)
- [Beamo Preloaded 64GB Raspberry Pi OS MicroSD Card](https://amzn.to/4x6SDe3) (affiliate link)
- [WiiM Mini AirPlay 2 Wireless Audio Streamer](https://amzn.to/4x09oHE) (affiliate link)
- [13.56Mhz USB RFID Reader](https://amzn.to/3RDH3GY) (affiliate link)
- [100 PCS 125KHz RFID Proximity ID Cards](https://amzn.to/4vhWsLx) (affiliate link)

## Install

```bash
pip install -r requirements.txt
```

Dependencies:

- `spotipy`
- `evdev`

## Configuration

The script uses `config.json` in the project root.

- If `config.json` does not exist, the script creates it with default values and exits.
- You can also start from `config.example.json`.
- Set `rfid.device_path` to your reader event device, for example `/dev/input/by-id/usb-YOUR_RFID_READER-event-kbd`.

Example config:

```json
{
    "spotify": {
        "client_id": "YOUR_SPOTIFY_CLIENT_ID",
        "client_secret": "YOUR_SPOTIFY_CLIENT_SECRET",
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
        "mapping_file": "rfid_spotify_map.json",
        "device_path": "/dev/input/by-id/usb-YOUR_RFID_READER-event-kbd"
    }
}
```

Notes:

- `wiim.match_mode` supports `contains` or `exact`.
- `wiim.initial_volume` is optional. If set, it is clamped to `0-100` before playback starts.
- On startup, the script merges missing defaults into an older `config.json` and writes the updated file back to disk.

## RFID Mapping File

`rfid.mapping_file` should point to a JSON file that maps card IDs to Spotify playlists.

Example:

```json
{
    "1234567890": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
    "9876543210": "https://open.spotify.com/playlist/37i9dQZF1DX4dyzvuaRJ0n",
    "1122334455": "37i9dQZF1DWXRqgorJj26U"
}
```

Playlist values can be any of these forms:

- A Spotify playlist URI
- A Spotify playlist URL
- A bare Spotify playlist ID

## First Run

The script authenticates with Spotify using OAuth and stores the token cache at `spotify.cache_path`.

On the first authenticated run, expect to complete the Spotify login flow in a browser.

## Usage

Start the RFID player:

```bash
python RFID_SPOTIFY_WIIM.py
```

List visible Spotify Connect devices:

```bash
python RFID_SPOTIFY_WIIM.py --list-devices
```

Test a playlist without scanning a card:

```bash
python RFID_SPOTIFY_WIIM.py --test-playlist spotify:playlist:37i9dQZF1DXcBWIGoYBM5M
```

Behavior at runtime:

- The script retries several times to find the configured WiiM device in Spotify Connect.
- If the RFID mapping file is missing or empty, it prints guidance and exits.
- If a card is scanned with no matching entry, it reports that and waits for the next scan.

## Raspberry Pi Service Setup

To run automatically on boot without a logged-in shell session:

1. Put the project in a stable location such as `/home/pi/RFID_Spotify`.
2. Verify `config.json`, especially `rfid.device_path`.
3. Create `/etc/systemd/system/rfid-spotify.service`:

```ini
[Unit]
Description=RFID Spotify Player
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/RFID_Spotify
ExecStart=/usr/bin/python3 /home/pi/RFID_Spotify/RFID_SPOTIFY_WIIM.py
Restart=always

[Install]
WantedBy=multi-user.target
```

4. Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rfid-spotify
sudo systemctl start rfid-spotify
```

5. Check status and logs:

```bash
sudo systemctl status rfid-spotify
journalctl -u rfid-spotify -f
```

If the service cannot open the RFID device, confirm the service user has permission to read the input device.

