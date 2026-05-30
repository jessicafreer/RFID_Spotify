# RFID_Spotify
Trigger a Spotify playlist using an RFID card

Pre-requisites:
Must have a Spotify premium account
Must get Spotify API client ID and secret
Must have a Raspberry Pi (I used 3b)
Must have a WIIM device as a connected device in your Spotify premium account (trust me - this is WAYYY easier than trying to make Raspberry Pi work with Bluetooth)
Must have RFID card reader
Must have programmable RFID cards

Copy config.example.json to config.json and fill in your local values.

Your config.json file should contain:
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
        "mapping_file": "rfid_spotify_map.json"
    }
}

