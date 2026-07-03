#!/usr/bin/env python3
"""
Raw Discord HTTP + Gateway client (no discord.py).

Uses a user token to react with an emoji on channel messages:
  - backfill: REST GET messages + PUT reactions
  - live: Gateway WebSocket MESSAGE_CREATE + PUT reactions
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, Literal

ReactionOutcome = Literal["ok", "permission_denied", "skipped"]
from urllib.parse import quote

import requests
from websocket import WebSocketApp

API_BASE = "https://discord.com/api/v10"
ISRAEL_FLAG = "\U0001f1ee\U0001f1f1"  # 🇮🇱
MESSAGE_CHANNEL_TYPES = {0, 5}  # text and announcement channels
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)


class RunTimer:
    def __init__(self, minutes: float) -> None:
        self.minutes = minutes
        self._deadline = time.monotonic() + minutes * 60 if minutes > 0 else None

    @property
    def limited(self) -> bool:
        return self._deadline is not None

    def expired(self) -> bool:
        return self._deadline is not None and time.monotonic() >= self._deadline

    def wait_up_to(self, seconds: float) -> bool:
        """Sleep up to seconds. Returns True if the timer expired."""
        if not self.limited:
            time.sleep(seconds)
            return False
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.expired():
                return True
            time.sleep(min(0.25, end - time.monotonic()))
        return self.expired()


@dataclass(frozen=True)
class ChannelSelection:
    all_channels: bool
    ids: tuple[int, ...]


def parse_channel_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    if not ids:
        raise argparse.ArgumentTypeError("at least one channel ID is required")
    return ids


def parse_channel_target(raw: str) -> ChannelSelection:
    if raw.strip().lower() == "all":
        return ChannelSelection(all_channels=True, ids=())
    return ChannelSelection(all_channels=False, ids=tuple(parse_channel_ids(raw)))


def parse_args() -> argparse.Namespace:
    channel_default = os.getenv("DISCORD_CHANNEL")
    parser = argparse.ArgumentParser(
        description="Raw HTTP/Gateway: emoji reactions in Discord channel(s).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--token",
        default=os.getenv("DISCORD_TOKEN"),
        help="User token (or set DISCORD_TOKEN)",
    )
    parser.add_argument("--emoji", default=os.getenv("DISCORD_EMOJI", ISRAEL_FLAG))
    parser.add_argument(
        "--channel",
        "--channels",
        type=parse_channel_target,
        default=parse_channel_target(channel_default) if channel_default else None,
        required=channel_default is None,
        metavar="ID[,ID...]|all",
        help="Channel ID(s), comma-separated, or 'all' for every accessible text channel",
    )
    guild_default = os.getenv("DISCORD_GUILD")
    parser.add_argument(
        "--guild",
        "--server",
        type=int,
        default=int(guild_default) if guild_default else None,
        required=guild_default is None,
        dest="guild",
        help="Server ID — channels must belong to this server (or set DISCORD_GUILD)",
    )
    backfill_group = parser.add_mutually_exclusive_group()
    backfill_group.add_argument(
        "--minutes",
        type=float,
        default=float(os.getenv("BACKFILL_MINUTES", "0")),
        help="Backfill messages from the last N minutes (0 = skip, default is live only)",
    )
    backfill_group.add_argument(
        "--last",
        type=int,
        default=int(os.getenv("BACKFILL_LAST", "0")),
        help="Backfill the last N messages per channel (0 = skip, default is live only)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="Seconds between reactions during backfill",
    )
    parser.add_argument("--skip-bots", action="store_true")
    parser.add_argument(
        "--skip-self",
        action="store_true",
        help="Do not react to your own messages (default: react to all messages)",
    )
    parser.add_argument(
        "--backfill-only",
        action="store_true",
        help="Run backfill then exit (no WebSocket)",
    )
    parser.add_argument(
        "--timer",
        type=float,
        default=float(os.getenv("RUN_MINUTES", "0")),
        help="Stop after N minutes (0 = run until Ctrl+C)",
    )
    return parser.parse_args()


class DiscordAPI:
    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": token,
                "Content-Type": "application/json",
                "User-Agent": CHROME_USER_AGENT,
            }
        )
        self.user_id: int | None = None

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{API_BASE}{path}"
        while True:
            response = self.session.request(method, url, **kwargs)
            if response.status_code != 429:
                return response
            try:
                retry = float(response.json().get("retry_after", 1.0))
            except (ValueError, requests.JSONDecodeError):
                retry = float(response.headers.get("Retry-After", 1.0))
            print(f"  rate limited, waiting {retry:.2f}s")
            time.sleep(retry)

    def me(self) -> dict[str, Any]:
        response = self.request("GET", "/users/@me")
        response.raise_for_status()
        data = response.json()
        self.user_id = int(data["id"])
        return data

    def get_channel(self, channel_id: int) -> dict[str, Any]:
        response = self.request("GET", f"/channels/{channel_id}")
        response.raise_for_status()
        return response.json()

    def list_guild_channels(self, guild_id: int) -> list[dict[str, Any]]:
        response = self.request("GET", f"/guilds/{guild_id}/channels")
        response.raise_for_status()
        return response.json()

    def fetch_messages(
        self,
        channel_id: int,
        *,
        limit: int = 100,
        before: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if before is not None:
            params["before"] = str(before)
        response = self.request("GET", f"/channels/{channel_id}/messages", params=params)
        response.raise_for_status()
        return response.json()

    def add_reaction(self, channel_id: int, message_id: int, emoji: str) -> ReactionOutcome:
        encoded = quote(emoji, safe="")
        path = f"/channels/{channel_id}/messages/{message_id}/reactions/{encoded}/@me"
        response = self.request("PUT", path)
        if response.status_code == 204:
            return "ok"
        if response.status_code == 403:
            try:
                if response.json().get("code") == 50013:
                    return "permission_denied"
            except (ValueError, requests.JSONDecodeError):
                pass
            body = response.text[:200]
            print(f"  skip {message_id}: HTTP 403 {body}")
            return "skipped"
        if response.status_code in (404, 400):
            body = response.text[:200]
            print(f"  skip {message_id}: HTTP {response.status_code} {body}")
            return "skipped"
        response.raise_for_status()
        return "skipped"

    def gateway_url(self) -> str:
        response = self.request("GET", "/gateway")
        response.raise_for_status()
        data = response.json()
        return f"{data['url']}?v=10&encoding=json"


def parse_timestamp(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def format_channel_label(
    channel_id: int,
    channel_by_id: dict[int, dict[str, Any]],
) -> str:
    channel = channel_by_id.get(channel_id)
    name = channel.get("name") if channel else None
    if name:
        return f"#{name} ({channel_id})"
    return str(channel_id)


def mark_channel_no_react(
    channel_id: int,
    skipped_channels: set[int],
    channel_by_id: dict[int, dict[str, Any]],
) -> None:
    if channel_id in skipped_channels:
        return
    skipped_channels.add(channel_id)
    print(
        f"  no react permission in {format_channel_label(channel_id, channel_by_id)} "
        "— skipping rest of channel"
    )


def should_process(
    message: dict[str, Any],
    user_id: int,
    *,
    skip_bots: bool,
    skip_self: bool,
) -> tuple[bool, str | None]:
    author = message.get("author", {})
    author_id = int(author.get("id", 0))
    if skip_self and author_id == user_id:
        return False, "own message (--skip-self)"
    if skip_bots and author.get("bot"):
        return False, "bot message (--skip-bots)"
    return True, None


def backfill_last(
    api: DiscordAPI,
    channel_id: int,
    emoji: str,
    count: int,
    delay: float,
    *,
    skip_bots: bool,
    skip_self: bool,
    timer: RunTimer,
    skipped_channels: set[int],
    channel_by_id: dict[int, dict[str, Any]],
) -> None:
    assert api.user_id is not None
    if channel_id in skipped_channels:
        return

    print(f"Backfill channel {channel_id}: last {count} message(s)")
    reacted = 0
    skipped = 0
    fetched = 0
    before: int | None = None

    while fetched < count:
        if timer.expired():
            print(f"Backfill stopped for {channel_id}: timer expired.")
            return

        batch = api.fetch_messages(
            channel_id,
            limit=min(100, count - fetched),
            before=before,
        )
        if not batch:
            break

        for message in batch:
            if timer.expired():
                print(f"Backfill stopped for {channel_id}: timer expired.")
                return
            fetched += 1
            ok, reason = should_process(
                message, api.user_id, skip_bots=skip_bots, skip_self=skip_self
            )
            if not ok:
                skipped += 1
                author = message.get("author", {}).get("username", "?")
                print(f"  skip {message['id']} from {author}: {reason}")
                continue

            outcome = api.add_reaction(channel_id, int(message["id"]), emoji)
            if outcome == "ok":
                reacted += 1
                print(f"  reacted on {message['id']}")
            elif outcome == "permission_denied":
                mark_channel_no_react(channel_id, skipped_channels, channel_by_id)
                print(
                    f"Backfill done for {channel_id}: {reacted} reaction(s), "
                    f"{skipped} skipped, {fetched} message(s) checked."
                )
                return
            if delay:
                time.sleep(delay)

            if fetched >= count:
                break

        before = int(batch[-1]["id"])

    print(
        f"Backfill done for {channel_id}: {reacted} reaction(s), {skipped} skipped, "
        f"{fetched} message(s) checked."
    )


def backfill(
    api: DiscordAPI,
    channel_id: int,
    emoji: str,
    minutes: float,
    delay: float,
    *,
    skip_bots: bool,
    skip_self: bool,
    timer: RunTimer,
    skipped_channels: set[int],
    channel_by_id: dict[int, dict[str, Any]],
) -> None:
    assert api.user_id is not None
    if channel_id in skipped_channels:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    print(f"Backfill channel {channel_id} since {cutoff.isoformat()}")

    scanned = 0
    reacted = 0
    skipped = 0
    before: int | None = None

    while True:
        if timer.expired():
            print(f"Backfill stopped for {channel_id}: timer expired.")
            return

        batch = api.fetch_messages(channel_id, limit=100, before=before)
        if not batch:
            break

        reached_cutoff = False
        for message in batch:
            if timer.expired():
                print(f"Backfill stopped for {channel_id}: timer expired.")
                return
            scanned += 1
            created = parse_timestamp(message["timestamp"])
            if created < cutoff:
                reached_cutoff = True
                break
            ok, reason = should_process(
                message, api.user_id, skip_bots=skip_bots, skip_self=skip_self
            )
            if not ok:
                skipped += 1
                author = message.get("author", {}).get("username", "?")
                print(f"  skip {message['id']} from {author}: {reason}")
                continue

            outcome = api.add_reaction(channel_id, int(message["id"]), emoji)
            if outcome == "ok":
                reacted += 1
                print(f"  reacted on {message['id']}")
            elif outcome == "permission_denied":
                mark_channel_no_react(channel_id, skipped_channels, channel_by_id)
                print(
                    f"Backfill done for {channel_id}: {reacted} reaction(s), "
                    f"{skipped} skipped, {scanned} message(s) checked."
                )
                return
            if delay:
                time.sleep(delay)

        if reached_cutoff:
            break

        before = int(batch[-1]["id"])

    print(
        f"Backfill done for {channel_id}: {reacted} reaction(s), {skipped} skipped, "
        f"{scanned} scanned message(s)."
    )


def run_gateway(
    api: DiscordAPI,
    token: str,
    channel_ids: frozenset[int],
    emoji: str,
    *,
    skip_bots: bool,
    skip_self: bool,
    timer: RunTimer,
    skipped_channels: set[int],
    channel_by_id: dict[int, dict[str, Any]],
) -> None:
    assert api.user_id is not None
    sequence: int | None = None
    heartbeat_stop = threading.Event()
    heartbeat_thread: threading.Thread | None = None
    sequence_lock = threading.Lock()

    def get_sequence() -> int | None:
        with sequence_lock:
            return sequence

    def set_sequence(value: int | None) -> None:
        nonlocal sequence
        with sequence_lock:
            sequence = value

    def send_json(ws: WebSocketApp, payload: dict[str, Any]) -> None:
        ws.send(json.dumps(payload))

    def start_heartbeat(ws: WebSocketApp, interval_ms: int) -> None:
        nonlocal heartbeat_thread

        def loop() -> None:
            interval = interval_ms / 1000.0
            while not heartbeat_stop.wait(interval):
                if timer.expired():
                    print(f"Timer expired after {timer.minutes} minute(s). Stopping.")
                    ws.close()
                    return
                send_json(ws, {"op": 1, "d": get_sequence()})

        heartbeat_stop.clear()
        heartbeat_thread = threading.Thread(target=loop, daemon=True)
        heartbeat_thread.start()

    def stop_heartbeat() -> None:
        heartbeat_stop.set()
        if heartbeat_thread and heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=2)

    def on_open(ws: WebSocketApp) -> None:
        print("Gateway connected.")

    def on_message(ws: WebSocketApp, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            print("Gateway: received invalid JSON")
            return

        op = payload.get("op")
        event = payload.get("t")
        data = payload.get("d")
        seq = payload.get("s")

        if isinstance(seq, int):
            set_sequence(seq)

        if op == 10 and isinstance(data, dict):
            start_heartbeat(ws, int(data["heartbeat_interval"]))
            send_json(
                ws,
                {
                    "op": 2,
                    "d": {
                        "token": token,
                        "properties": {
                            "$os": "windows",
                            "$browser": "chrome",
                            "$device": "chrome",
                        },
                        "presence": {
                            "status": "online",
                            "since": 0,
                            "activities": [],
                            "afk": False,
                        },
                    },
                },
            )
            return

        if op == 11:
            return

        if op == 0 and event == "READY" and isinstance(data, dict):
            user = data.get("user", {})
            if len(channel_ids) <= 10:
                watched = ", ".join(str(channel_id) for channel_id in sorted(channel_ids))
            else:
                watched = f"{len(channel_ids)} channels"
            print(f"Gateway ready as {user.get('username')} — watching {watched}")
            return

        if op == 0 and event == "MESSAGE_CREATE" and isinstance(data, dict):
            message_channel_id = int(data.get("channel_id", 0))
            if message_channel_id not in channel_ids:
                return
            if message_channel_id in skipped_channels:
                return
            ok, reason = should_process(
                data, api.user_id, skip_bots=skip_bots, skip_self=skip_self
            )
            if not ok:
                author = data.get("author", {}).get("username", "unknown")
                print(f"skip new message from {author}: {reason}")
                return
            message_id = int(data["id"])
            outcome = api.add_reaction(message_channel_id, message_id, emoji)
            if outcome == "ok":
                author = data.get("author", {}).get("username", "unknown")
                print(f"reacted on new message from {author} in {message_channel_id}")
            elif outcome == "permission_denied":
                mark_channel_no_react(
                    message_channel_id, skipped_channels, channel_by_id
                )
            return

        if op == 7:
            stop_heartbeat()
            ws.close()
            return

        if op == 9 and isinstance(data, dict):
            print("Invalid session, reconnecting...")
            stop_heartbeat()
            ws.close()

    def on_error(_ws: WebSocketApp, error: Exception) -> None:
        print(f"Gateway error: {error}")

    def on_close(_ws: WebSocketApp, status: int | None, msg: str | None) -> None:
        stop_heartbeat()
        print(f"Gateway closed ({status}): {msg}")

    while True:
        if timer.expired():
            print(f"Timer expired after {timer.minutes} minute(s). Stopping.")
            return

        try:
            gateway = api.gateway_url()
        except requests.HTTPError as exc:
            print(f"Failed to get gateway URL: {exc}")
            if timer.wait_up_to(5):
                print(f"Timer expired after {timer.minutes} minute(s). Stopping.")
                return
            continue

        ws = WebSocketApp(
            gateway,
            header=[f"User-Agent: {CHROME_USER_AGENT}"],
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        try:
            ws.run_forever()
        except KeyboardInterrupt:
            stop_heartbeat()
            print("\nStopped.")
            return
        stop_heartbeat()
        set_sequence(None)
        if timer.expired():
            print(f"Timer expired after {timer.minutes} minute(s). Stopping.")
            return
        print("Reconnecting in 5s...")
        if timer.wait_up_to(5):
            print(f"Timer expired after {timer.minutes} minute(s). Stopping.")
            return


def validate_guild_channel(channel: dict[str, Any], channel_id: int, guild_id: int) -> bool:
    channel_guild = channel.get("guild_id")
    if channel_guild is None or int(channel_guild) != guild_id:
        print(
            f"Error: channel {channel_id} is not in server {guild_id}.",
            file=sys.stderr,
        )
        sys.exit(1)
    return True


def resolve_channels(
    api: DiscordAPI,
    channel_ids: list[int],
    guild_id: int,
) -> list[dict[str, Any]]:
    channels: list[dict[str, Any]] = []
    for channel_id in channel_ids:
        try:
            channel = api.get_channel(channel_id)
        except requests.HTTPError as exc:
            print(f"Error: cannot access channel {channel_id} ({exc})", file=sys.stderr)
            sys.exit(1)

        validate_guild_channel(channel, channel_id, guild_id)
        channels.append(channel)
    return channels


def resolve_all_channels(
    api: DiscordAPI,
    guild_id: int,
) -> tuple[list[int], list[dict[str, Any]]]:
    try:
        guild_channels = api.list_guild_channels(guild_id)
    except requests.HTTPError as exc:
        print(f"Error: cannot list channels for server {guild_id} ({exc})", file=sys.stderr)
        sys.exit(1)

    candidates = sorted(
        (
            channel
            for channel in guild_channels
            if int(channel.get("type", -1)) in MESSAGE_CHANNEL_TYPES
        ),
        key=lambda channel: int(channel.get("position", 0)),
    )

    channel_ids: list[int] = []
    channels: list[dict[str, Any]] = []
    for candidate in candidates:
        channel_id = int(candidate["id"])
        name = candidate.get("name", str(channel_id))
        try:
            channel = api.get_channel(channel_id)
        except requests.HTTPError:
            print(f"Warning: skipping #{name} ({channel_id}): no access", file=sys.stderr)
            continue
        validate_guild_channel(channel, channel_id, guild_id)
        channel_ids.append(channel_id)
        channels.append(channel)

    if not channel_ids:
        print("Error: no accessible text channels found in server.", file=sys.stderr)
        sys.exit(1)

    print(f"Resolved {len(channel_ids)} accessible text channel(s) in server {guild_id}.")
    return channel_ids, channels


def main() -> None:
    args = parse_args()
    if not args.token:
        print("Error: --token is required (or set DISCORD_TOKEN).", file=sys.stderr)
        sys.exit(1)

    api = DiscordAPI(args.token)
    try:
        me = api.me()
    except requests.HTTPError:
        print("Error: invalid token or API failure on /users/@me.", file=sys.stderr)
        sys.exit(1)

    if args.channel.all_channels:
        channel_ids, channels = resolve_all_channels(api, args.guild)
    else:
        channel_ids = list(dict.fromkeys(args.channel.ids))
        if len(channel_ids) < len(args.channel.ids):
            print("Warning: duplicate channel IDs were removed.", file=sys.stderr)
        channels = resolve_channels(api, channel_ids, args.guild)

    if len(channel_ids) <= 10:
        channel_labels = [
            f"#{channel.get('name') or channel_id}"
            for channel, channel_id in zip(channels, channel_ids)
        ]
        channel_summary = ", ".join(channel_labels)
    else:
        channel_summary = f"{len(channel_ids)} channels"
    print(
        f"User: {me['username']} | channel(s) {channel_summary} | "
        f"server {args.guild} | emoji {args.emoji!r}"
    )

    timer = RunTimer(args.timer)
    skipped_channels: set[int] = set()
    channel_by_id = {int(channel["id"]): channel for channel in channels}

    if args.last > 0:
        for channel_id in channel_ids:
            if timer.expired():
                print(f"Timer expired after {args.timer} minute(s). Stopping.")
                return
            backfill_last(
                api,
                channel_id,
                args.emoji,
                args.last,
                args.delay,
                skip_bots=args.skip_bots,
                skip_self=args.skip_self,
                timer=timer,
                skipped_channels=skipped_channels,
                channel_by_id=channel_by_id,
            )
    elif args.minutes > 0:
        for channel_id in channel_ids:
            if timer.expired():
                print(f"Timer expired after {args.timer} minute(s). Stopping.")
                return
            backfill(
                api,
                channel_id,
                args.emoji,
                args.minutes,
                args.delay,
                skip_bots=args.skip_bots,
                skip_self=args.skip_self,
                timer=timer,
                skipped_channels=skipped_channels,
                channel_by_id=channel_by_id,
            )

    if skipped_channels:
        print(
            f"No react permission in {len(skipped_channels)} channel(s); "
            "those channels will be skipped for the rest of this run."
        )

    if args.backfill_only or timer.expired():
        if timer.expired():
            print(f"Timer expired after {args.timer} minute(s). Stopping.")
        return

    if timer.limited:
        print(
            f"Listening via Gateway WebSocket. Stops after {args.timer} minute(s). "
            "Ctrl+C to stop early."
        )
    else:
        print("Listening via Gateway WebSocket. Ctrl+C to stop.")
    run_gateway(
        api,
        args.token,
        frozenset(channel_ids),
        args.emoji,
        skip_bots=args.skip_bots,
        skip_self=args.skip_self,
        timer=timer,
        skipped_channels=skipped_channels,
        channel_by_id=channel_by_id,
    )


if __name__ == "__main__":
    main()