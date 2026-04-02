#!/usr/bin/env python3
# ─────────────────────────────────────────────
#  igxdbot — Instagram Downloader Telegram Bot
#  Built with Telethon  |  @CoderAjinkya
# ─────────────────────────────────────────────

import asyncio
import re
import aiohttp
import aiosqlite
from io import BytesIO

from telethon import TelegramClient, events, Button
from telethon.errors import (
    UserIsBlockedError,
    InputUserDeactivatedError,
    FloodWaitError,
    ChatWriteForbiddenError,
    PeerIdInvalidError,
)


# ════════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════════════════════════

BOT_TOKEN    = "8728597984:AAFsH9-XOdvYvucggIN_ivADwMaTERI-X-U"
API_ID       = 26163553
API_HASH     = "1ecd6d8b71cbda6f66aa7415947d4538"
OWNER_ID     = 5540313415
DOWNLOAD_API = "https://apis.prexzyvilla.site/download/instagram?url="
DB_PATH      = "users.db"
SESSION_NAME = "igxdbot_session"


# ════════════════════════════════════════════════════════════════════════════════
#  DATABASE  (SQLite, local VPS storage)
# ════════════════════════════════════════════════════════════════════════════════

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                first_name TEXT,
                username   TEXT,
                joined_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def add_user(user_id: int, first_name: str, username) -> bool:
    """Returns True if brand-new user, False if already exists."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if await cur.fetchone():
            return False
        await db.execute(
            "INSERT INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
            (user_id, first_name or "Unknown", username),
        )
        await db.commit()
        return True


async def get_user_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        return row[0] if row else 0


async def get_all_users() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users")
        return [r[0] for r in await cur.fetchall()]


# ════════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════════

IG_REGEX = re.compile(
    r"https?://(?:www\.)?instagram\.com/"
    r"(?:p|reel|tv|stories(?:/[^/\s]+)?)/[^\s?#]+(?:[?#][^\s]*)?"
)

broadcast_states: dict = {}

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


async def fetch_ig_info(url: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                DOWNLOAD_API + url,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
                if not data.get("status"):
                    return None

                result = data.get("data", {})
                if "caption" in result:
                    del result["caption"]

                return result
    except Exception:
        return None


async def download_to_bytes(url: str, filename: str) -> BytesIO | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    return None
                bio = BytesIO(await resp.read())
                bio.name = filename
                return bio
    except Exception:
        return None


async def answer_inline_via_bot_api(inline_query_id: str, results: list) -> None:
    """Answer inline queries via HTTP Bot API (supports bare web-URLs for media)."""
    endpoint = f"https://api.telegram.org/bot{BOT_TOKEN}/answerInlineQuery"
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                endpoint,
                json={"inline_query_id": inline_query_id, "results": results,
                      "cache_time": 0, "is_personal": True},
                timeout=aiohttp.ClientTimeout(total=10),
            )
    except Exception:
        pass


async def _copy_message_to_user(uid: int, post_msg) -> None:
    if post_msg.media:
        await client.send_file(
            uid,
            post_msg.media,
            caption=post_msg.message or "",
            formatting_entities=post_msg.entities or None,
        )
    else:
        await client.send_message(
            uid,
            post_msg.message or "",
            formatting_entities=post_msg.entities or None,
        )


# ════════════════════════════════════════════════════════════════════════════════
#  /start
# ════════════════════════════════════════════════════════════════════════════════

@client.on(events.NewMessage(pattern="/start", incoming=True, func=lambda e: e.is_private))
async def start_handler(event):
    user = await event.get_sender()

    is_new = await add_user(user.id, user.first_name, user.username)

    if is_new:
        total = await get_user_count()
        notif = (
            "🆕 <b>New User Notification</b> 🆕\n\n"
            f"👩‍💻 Name : {user.first_name or 'N/A'}\n"
            f"👉 Username : @{user.username or 'N/A'}\n"
            f"🔗 User Link : <a href='tg://user?id={user.id}'>{user.first_name or 'User'}</a>\n"
            f"🆔 User ID : <code>{user.id}</code>\n\n"
            f"📊 Total Users : {total}"
        )
        try:
            await client.send_message(OWNER_ID, notif, parse_mode="html")
        except Exception:
            pass

    name_link = f"<a href='tg://settings'>{user.first_name or 'User'}</a>"
    welcome = (
        f"👋 Hello! <b>{name_link}</b>\n\n"
        "Welcome to the fastest bot for downloading photos, videos, and stories from Instagram.\n\n"
        "Send me a link from Instagram to download:\n"
        "┣━ 🖼 Post\n"
        "┣━ 🎬 Reels\n"
        "┗━ 🎞 Stories\n\n"
        "🔎 <u>Use Inline Mode in Any Chat:</u>\n"
        "Example: <b>@igxdbot + link</b>\n\n"
        "<blockquote>👨‍💻 Created By @CoderAjinkya</blockquote>"
    )
    buttons = [
        [Button.switch_inline("🤖 Inline Mode", query="", same_peer=True)],
        [
            Button.url("🔗 Join Channel", "https://t.me/kids_coder"),
            Button.url("🔗 Join Channel", "https://t.me/asxdev"),
        ],
    ]
    await event.reply(welcome, buttons=buttons, parse_mode="html", link_preview=False)


# ════════════════════════════════════════════════════════════════════════════════
#  /admin  (owner only)
# ════════════════════════════════════════════════════════════════════════════════

@client.on(events.NewMessage(pattern="/admin", incoming=True))
async def admin_handler(event):
    if event.sender_id != OWNER_ID:
        return
    total = await get_user_count()
    await event.reply(
        f"👑 <b>Admin Panel</b>\n\n📊 Total Users: <b>{total}</b>\n\nChoose an option:",
        parse_mode="html",
        buttons=[
            [Button.inline("📢 Broadcast", data="bc:start")],
            [Button.inline("📊 Stats", data="bc:stats")],
        ],
    )


# ════════════════════════════════════════════════════════════════════════════════
#  /cancel  (owner only)
# ════════════════════════════════════════════════════════════════════════════════

@client.on(events.NewMessage(pattern="/cancel", incoming=True))
async def cancel_handler(event):
    if event.sender_id != OWNER_ID:
        return
    if OWNER_ID in broadcast_states:
        broadcast_states.pop(OWNER_ID)
        await event.reply("❌ <b>Broadcast cancelled.</b>", parse_mode="html")


# ════════════════════════════════════════════════════════════════════════════════
#  CALLBACK QUERIES
# ════════════════════════════════════════════════════════════════════════════════

@client.on(events.CallbackQuery(data=b"bc:start"))
async def cb_broadcast_start(event):
    if event.sender_id != OWNER_ID:
        await event.answer("❌ Not authorized!", alert=True)
        return
    broadcast_states[OWNER_ID] = {"state": "waiting_post"}
    await event.edit(
        "📢 <b>Broadcast Mode</b>\n\n"
        "Send me the post to broadcast:\n"
        "• Text (bold / italic preserved)\n"
        "• Photo + caption\n"
        "• Video + caption\n\n"
        "Send /cancel to abort.",
        parse_mode="html",
    )


@client.on(events.CallbackQuery(data=b"bc:stats"))
async def cb_stats(event):
    if event.sender_id != OWNER_ID:
        await event.answer("❌ Not authorized!", alert=True)
        return
    total = await get_user_count()
    await event.edit(
        f"📊 <b>Bot Statistics</b>\n\n👥 Total Users: <b>{total}</b>",
        parse_mode="html",
        buttons=[[Button.inline("🔙 Back", data="bc:back")]],
    )


@client.on(events.CallbackQuery(data=b"bc:back"))
async def cb_back(event):
    if event.sender_id != OWNER_ID:
        return
    total = await get_user_count()
    await event.edit(
        f"👑 <b>Admin Panel</b>\n\n📊 Total Users: <b>{total}</b>\n\nChoose an option:",
        parse_mode="html",
        buttons=[
            [Button.inline("📢 Broadcast", data="bc:start")],
            [Button.inline("📊 Stats", data="bc:stats")],
        ],
    )


@client.on(events.CallbackQuery(data=b"bc:confirm"))
async def cb_broadcast_confirm(event):
    if event.sender_id != OWNER_ID:
        await event.answer("❌ Not authorized!", alert=True)
        return
    state = broadcast_states.get(OWNER_ID, {})
    post_msg = state.get("post_message")
    if not post_msg:
        await event.answer("❌ No post stored!", alert=True)
        return

    await event.edit("📢 <b>Broadcasting…</b>\n\n⏳ Starting…", parse_mode="html")
    progress_msg = await event.get_message()

    users = await get_all_users()
    total = len(users)
    success = failed = 0

    for idx, uid in enumerate(users, start=1):
        try:
            await _copy_message_to_user(uid, post_msg)
            success += 1
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 2)
            try:
                await _copy_message_to_user(uid, post_msg)
                success += 1
            except Exception:
                failed += 1
        except (UserIsBlockedError, InputUserDeactivatedError,
                ChatWriteForbiddenError, PeerIdInvalidError):
            failed += 1
        except Exception:
            failed += 1

        if idx % 10 == 0 or idx == total:
            try:
                await progress_msg.edit(
                    f"📢 <b>Broadcasting…</b>\n\n"
                    f"📊 Progress : <b>{idx} / {total}</b>\n"
                    f"✅ Success  : <b>{success}</b>\n"
                    f"❌ Failed   : <b>{failed}</b>",
                    parse_mode="html",
                )
            except Exception:
                pass

        await asyncio.sleep(0.05)

    broadcast_states.pop(OWNER_ID, None)
    await progress_msg.edit(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"👥 Total Users : <b>{total}</b>\n"
        f"✅ Success     : <b>{success}</b>\n"
        f"❌ Failed      : <b>{failed}</b>",
        parse_mode="html",
    )


@client.on(events.CallbackQuery(data=b"bc:cancel"))
async def cb_broadcast_cancel(event):
    if event.sender_id != OWNER_ID:
        return
    broadcast_states.pop(OWNER_ID, None)
    await event.edit("❌ <b>Broadcast cancelled.</b>", parse_mode="html")


# ════════════════════════════════════════════════════════════════════════════════
#  INSTAGRAM DOWNLOAD  (private + groups + supergroups)
# ════════════════════════════════════════════════════════════════════════════════

@client.on(events.NewMessage(incoming=True))
async def message_handler(event):
    msg_text = event.text or ""
    if msg_text.startswith("/"):
        return

    sender = await event.get_sender()
    if sender is None:
        return

    # ── Owner broadcast: capture post ────────────────────────────────────────
    if sender.id == OWNER_ID:
        state = broadcast_states.get(OWNER_ID, {})
        if state.get("state") == "waiting_post":
            broadcast_states[OWNER_ID]["state"] = "preview"
            broadcast_states[OWNER_ID]["post_message"] = event.message
            await event.reply(
                "👁 <b>Broadcast Preview</b>\n\n"
                "The message above will be sent to all users.\n\nConfirm or cancel:",
                parse_mode="html",
                buttons=[
                    [Button.inline("✅ Confirm & Send", data="bc:confirm")],
                    [Button.inline("❌ Cancel", data="bc:cancel")],
                ],
            )
            return

    # ── Instagram link detection ──────────────────────────────────────────────
    match = IG_REGEX.search(msg_text)
    if not match:
        return

    ig_url = match.group(0)

    status = await event.reply(
        "<b>⬇️ Downloading Media (Fast Mode) . . .</b>",
        parse_mode="html",
    )

    data = await fetch_ig_info(ig_url)
    if not data:
        await status.edit("<b>❌ Failed to fetch media!</b>", parse_mode="html")
        return

    is_video = data.get("isVideo", False)
    media_urls = data.get("url", [])

    if not media_urls:
        await status.edit("<b>❌ Failed to fetch media!</b>", parse_mode="html")
        return

    try:
        # ── VIDEO ─────────────────────────────────────────────────────────────
        if is_video:
            await status.edit("<b>✅ Media Downloaded</b>", parse_mode="html")
            await status.edit("<b>📤 Uploading Video . . .</b>", parse_mode="html")
            async with client.action(event.chat_id, "video"):
                bio = await download_to_bytes(media_urls[0], "reel.mp4")
                if not bio:
                    await status.edit("<b>❌ Failed to fetch media!</b>", parse_mode="html")
                    return
                await client.send_file(
                    event.chat_id, bio,
                    reply_to=event.id,
                    supports_streaming=True,
                    force_document=False,
                    video_note=False,
                )
            await status.delete()

        # ── PHOTO ─────────────────────────────────────────────────────────────
        else:
            await status.edit("<b>✅ Media Downloaded</b>", parse_mode="html")
            await status.edit("<b>📤 Uploading Photo . . .</b>", parse_mode="html")
            async with client.action(event.chat_id, "photo"):
                if len(media_urls) == 1:
                    bio = await download_to_bytes(media_urls[0], "photo.jpg")
                    if not bio:
                        await status.edit("<b>❌ Failed to fetch media!</b>", parse_mode="html")
                        return
                    await client.send_file(
                        event.chat_id, bio,
                        reply_to=event.id, force_document=False,
                    )
                else:
                    files = []
                    for i, url in enumerate(media_urls):
                        bio = await download_to_bytes(url, f"photo_{i}.jpg")
                        if bio:
                            files.append(bio)
                    if not files:
                        await status.edit("<b>❌ Failed to fetch media!</b>", parse_mode="html")
                        return
                    await client.send_file(
                        event.chat_id, files,
                        reply_to=event.id, force_document=False,
                    )
            await status.delete()

    except Exception:
        try:
            await status.edit("<b>❌ Failed to fetch media!</b>", parse_mode="html")
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════════
#  INLINE QUERY
# ════════════════════════════════════════════════════════════════════════════════

@client.on(events.InlineQuery)
async def inline_handler(event):
    query = (event.text or "").strip()
    qid   = str(event.id)

    if not query:
        await answer_inline_via_bot_api(qid, [{
            "type": "article", "id": "0",
            "title": "📥 Paste Instagram Link",
            "description": "🔗 Paste link to fetch reel or post",
            "input_message_content": {"message_text": "✨ Paste your Instagram link to fetch reel or post!"},
            "thumbnail_url": "https://cdn-icons-png.flaticon.com/128/1384/1384063.png",
        }])
        return

    match = IG_REGEX.search(query)
    if not match:
        await _inline_no_result(qid)
        return

    data = await fetch_ig_info(match.group(0))
    if not data:
        await _inline_no_result(qid)
        return

    is_video = data.get("isVideo", False)
    media_urls = data.get("url", [])
    results = []

    if is_video:
        fixed_thumb = "https://cdn-icons-png.flaticon.com/128/11820/11820224.png"
        for i, url in enumerate(media_urls):
            results.append({
                "type": "video", "id": f"v_{i}",
                "video_url": url, "mime_type": "video/mp4",
                "thumbnail_url": fixed_thumb,
                "title": "🎬 Reel Fetched Successfully",
                "description": "Tap to send reel 🚀",
            })
    else:
        for i, url in enumerate(media_urls):
            results.append({
                "type": "photo", "id": f"p_{i}",
                "photo_url": url, "thumbnail_url": url,
                "photo_width": 512, "photo_height": 512,
            })

    await (answer_inline_via_bot_api(qid, results) if results else _inline_no_result(qid))


async def _inline_no_result(qid: str) -> None:
    await answer_inline_via_bot_api(qid, [{
        "type": "article", "id": "no_result",
        "title": "❌ No Result Found",
        "description": "Try another Instagram link 😕",
        "input_message_content": {"message_text": "❌ No media found!\n\nPlease send a valid Instagram link 📎"},
        "thumbnail_url": "https://cdn-icons-png.flaticon.com/128/2748/2748614.png",
    }])


# ════════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    await init_db()
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()
    print(f"✅  Bot started as @{me.username}  |  ID: {me.id}")
    print("📌  Press Ctrl+C to stop.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
