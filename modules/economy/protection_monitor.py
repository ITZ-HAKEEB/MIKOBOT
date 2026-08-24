import time
import asyncio
from modules.utils.storage import get_all_users, update_user


async def start_protection_monitor(bot):
    """Background monitor that sends automated warning alerts to users in private DM
    at 6 Hours, 2 Hours, and 30 Minutes before their /protect expires."""
    print("🛡️ Protection Expiry Alert Monitor started...")
    while True:
        try:
            now_ts = time.time()
            all_users = get_all_users()

            for uid_str, ud in all_users.items():
                if not isinstance(ud, dict):
                    continue

                if not ud.get("protected"):
                    continue

                protected_until = ud.get("protected_until") or 0
                if not protected_until:
                    continue

                try:
                    uid = int(uid_str)
                except ValueError:
                    continue

                rem = protected_until - now_ts

                # If protection has already expired
                if rem <= 0:
                    update_user(uid, protected=False, protected_until=0, protection_alerts=[])
                    continue

                alerts_sent = set(ud.get("protection_alerts") or [])

                # 1. Alert at 30 Minutes
                if rem <= 30 * 60:
                    if "30m" not in alerts_sent:
                        alerts_sent.add("30m")
                        alerts_sent.add("2h")
                        alerts_sent.add("6h")
                        update_user(uid, protection_alerts=list(alerts_sent))
                        msg = (
                            "⚠️ Aʟᴇʀᴛ!\n\n"
                            "Yᴏᴜʀ Pʀᴏᴛᴇᴄᴛɪᴏɴ Wɪʟʟ Eɴᴅ Iɴ Exᴀᴄᴛʟʏ 30 Mɪɴᴜᴛᴇꜱ.\n"
                            "👉 Uꜱᴇ /protect Tᴏ Sᴛᴀʏ Sᴀғᴇ."
                        )
                        try:
                            await bot.send_message(chat_id=uid, text=msg)
                        except Exception:
                            pass

                # 2. Alert at 2 Hours
                elif rem <= 2 * 3600:
                    if "2h" not in alerts_sent:
                        alerts_sent.add("2h")
                        alerts_sent.add("6h")
                        update_user(uid, protection_alerts=list(alerts_sent))
                        msg = (
                            "⚠️ Aʟᴇʀᴛ!\n\n"
                            "Yᴏᴜʀ Pʀᴏᴛᴇᴄᴛɪᴏɴ Wɪʟʟ Eɴᴅ Iɴ Exᴀᴄᴛʟʏ 2 Hᴏᴜʀꜱ.\n"
                            "👉 Uꜱᴇ /protect Tᴏ Sᴛᴀʏ Sᴀғᴇ."
                        )
                        try:
                            await bot.send_message(chat_id=uid, text=msg)
                        except Exception:
                            pass

                # 3. Alert at 6 Hours
                elif rem <= 6 * 3600:
                    if "6h" not in alerts_sent:
                        alerts_sent.add("6h")
                        update_user(uid, protection_alerts=list(alerts_sent))
                        msg = (
                            "⚠️ Aʟᴇʀᴛ!\n\n"
                            "Yᴏᴜʀ Pʀᴏᴛᴇᴄᴛɪᴏɴ Wɪʟʟ Eɴᴅ Iɴ Exᴀᴄᴛʟʏ 6 Hᴏᴜʀꜱ.\n"
                            "👉 Uꜱᴇ /protect Tᴏ Sᴛᴀʏ Sᴀғᴇ."
                        )
                        try:
                            await bot.send_message(chat_id=uid, text=msg)
                        except Exception:
                            pass

        except Exception as e:
            print(f"⚠️ Protection monitor notice: {e}")

        # Check every 45 seconds
        await asyncio.sleep(45)
