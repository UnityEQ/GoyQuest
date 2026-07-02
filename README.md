# Goyquest

Lightweight CLI tool that reacts to Discord channel messages with the Israeli flag emoji (🇮🇱) using the raw Discord HTTP API and Gateway WebSocket — no `discord.py`.

## What it does

- **Live (default)** — watches for new messages via WebSocket and reacts in real time
- **Backfill (optional)** — on startup, react to recent messages by time (`--minutes`) or message count (`--last`)
- **Run timer (optional)** — stop automatically after N minutes, or run until Ctrl+C (default)
- **One or more channels** — pass channel IDs via `--channel`, or use `--channel all` for every accessible text channel in the server

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

**Single channel (live only — default):**

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

**All text channels in the server:**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel all
```

`--channel all` (or `--channels all`) discovers every text and announcement channel in the server that your account can access. Channels you cannot read are skipped.

`--server` is an alias for `--guild`.

**Run timer (optional):**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789                # run until Ctrl+C (default)
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --timer 30   # stop after 30 minutes
```

The timer counts from script start and applies to backfill and live listening.

**Backfill by time (optional, in minutes):**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789                    # live only (default)
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --minutes 60   # backfill last 60 minutes, then live
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --minutes 1440 # backfill last 24 hours, then live
```

**Backfill by message count:**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --last 30   # react on the 30 most recent messages, then live
```

Use `--minutes` or `--last`, not both. `--last` applies per channel.

**Backfill only (no WebSocket):**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --minutes 60 --backfill-only
```

**Backfill, then live, with a run timer:**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --minutes 60 --timer 120
```

Backfills the last 60 minutes, then listens for new messages, and stops after 120 minutes total (including backfill).

**Validate token and channel access (no reactions, no WebSocket):**

```powershell
python react_http.py --token YOUR_TOKEN --server 1111111111111111111 --channel 1234567890123456789 --backfill-only
```

Checks your token, server, and channel IDs via the REST API, then exits.

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--token` | *(required)* | User token |
| `--channel`, `--channels` | *(required)* | Channel ID(s), comma-separated, or `all` for every accessible text channel |
| `--guild`, `--server` | *(required)* | Server ID — channels must belong to this server |
| `--emoji` | 🇮🇱 | Emoji to react with |
| `--minutes` | `0` | Backfill messages from the last N minutes (`0` = skip) |
| `--last` | `0` | Backfill the last N messages per channel (`0` = skip) |
| `--delay` | `0.35` | Seconds between reactions during backfill |
| `--skip-bots` | off | Ignore messages from bots |
| `--skip-self` | off | Skip your own messages |
| `--backfill-only` | off | Backfill then exit |
| `--timer` | `0` | Stop after N minutes (`0` = run until Ctrl+C) |

| Environment variable | CLI flag |
|---------------------|----------|
| `DISCORD_TOKEN` | `--token` |
| `DISCORD_CHANNEL` | `--channel` (comma-separated IDs or `all`) |
| `DISCORD_GUILD` | `--server` / `--guild` |
| `DISCORD_EMOJI` | `--emoji` |
| `BACKFILL_MINUTES` | `--minutes` |
| `BACKFILL_LAST` | `--last` |
| `RUN_MINUTES` | `--timer` |

If `DISCORD_TOKEN`, `DISCORD_GUILD`, and `DISCORD_CHANNEL` are set, you can omit `--token`, `--server`, and `--channel` on the command line. Set `DISCORD_CHANNEL=all` to use all channels. Put secrets in a `.env` file locally — it is gitignored.

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
├── .gitignore
└── README.md
```

## Notes

- Automating a user account may violate Discord's Terms of Service. Use at your own risk.
- Do not commit tokens to public repositories.
- Press **Ctrl+C** in the terminal to stop early (even when `--timer` is set).
- Windows PowerShell may not display 🇮🇱 in the console; reactions still work on Discord.