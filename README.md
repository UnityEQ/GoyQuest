# Goyquest

Lightweight CLI tool that reacts to Discord channel messages with the Israeli flag emoji (🇮🇱) using the raw Discord HTTP API and Gateway WebSocket — no `discord.py`.

## What it does

- **Backfill** — on startup, reacts to messages from the last N hours in your target channel(s)
- **Live** — watches for new messages via WebSocket and reacts in real time
- **One or more channels** — pass a single channel ID or comma-separated IDs via `--channel`

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`
- Your Discord user token, server ID, and at least one channel ID

## Setup

```powershell
cd goyquest
python -m pip install -r requirements.txt
```

## Getting your token

To get the token for your personal account:

> Automating user accounts is technically against TOS — use at your own risk!

1. Open Discord in your web browser and login
2. Open any server or direct message channel
3. Press Ctrl+Shift+I to show developer tools
4. Navigate to the Network tab
5. Press Ctrl+R to reload
6. Switch between random channels to trigger network requests
7. Search for a request that starts with `messages`
8. Select the Headers tab on the right
9. Scroll down to the Request Headers section
10. Copy the value of the `authorization` header

## Getting channel and server IDs

You need a server ID for `--server` and at least one channel ID for `--channel`.

1. Open Discord (desktop app or web browser)
2. Click the gear icon next to your username to open **User Settings**
3. Go to **Advanced** in the left sidebar
4. Turn on **Developer Mode**
5. Close settings

**Server ID:**

1. In the server list on the left, right-click the server icon (the circular image)
2. Click **Copy Server ID**
3. Paste it into `--server` (e.g. `--server 1111111111111111111`)

**Channel ID:**

1. Right-click the text channel name in the channel list
2. Click **Copy Channel ID**
3. Paste it into `--channel` (e.g. `--channel 1234567890123456789`)

For multiple channels, copy each channel ID and separate them with commas.

Example: `--server 1111111111111111111 --channel 1234567890123456789,9876543210987654321`

## Usage

**Single channel (backfill last hour, then watch for new messages):**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789
```

Or:

```powershell
.\run.ps1 --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789
```

**Multiple channels (comma-separated):**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789,9876543210987654321
```

`--server` is an alias for `--guild`. Every channel ID must belong to that server.

**Backfill window:**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789              # last 1 hour (default)
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --hours 24 # last 24 hours
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --hours 0  # skip backfill, live only
```

**Backfill only (no WebSocket):**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --backfill-only
```

**Test connection without reacting:**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --backfill-only --hours 0
```

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--token` | *(required)* | User token |
| `--channel` | *(required)* | Target channel ID(s), comma-separated for multiple |
| `--guild`, `--server` | *(required)* | Server ID — channels must belong to this server |
| `--emoji` | 🇮🇱 | Emoji to react with |
| `--hours` | `1` | Backfill window in hours (`0` = skip) |
| `--delay` | `0.35` | Seconds between reactions during backfill |
| `--skip-bots` | off | Ignore messages from bots |
| `--skip-self` | off | Skip your own messages |
| `--backfill-only` | off | Backfill then exit |

Environment variables: `DISCORD_TOKEN`, `DISCORD_CHANNEL`, `DISCORD_GUILD`, `DISCORD_EMOJI`, `BACKFILL_HOURS`

If `DISCORD_TOKEN`, `DISCORD_GUILD`, and `DISCORD_CHANNEL` are set, you can omit `--token`, `--server`, and `--channel` on the command line.

## How it works

| Phase | Method |
|-------|--------|
| Auth | `Authorization: <token>` on REST requests |
| Backfill | `GET /channels/{id}/messages` → `PUT .../reactions/{emoji}/@me` |
| Live | Gateway WebSocket `MESSAGE_CREATE` → `PUT` reaction |

## Project layout

```
goyquest/
├── react_http.py    # Main script
├── requirements.txt
├── run.ps1          # PowerShell launcher
└── README.md
```

## Notes

- Automating a user account may violate Discord's Terms of Service. Use at your own risk.
- Do not commit tokens to public repositories.
- Windows PowerShell may not display 🇮🇱 in the console; reactions still work on Discord.