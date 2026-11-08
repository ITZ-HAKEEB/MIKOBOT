# 🌸 Miko — Multi-Feature Telegram Bot

An advanced, feature-rich Telegram bot featuring Economy, Mini-Games, AI DM Chatbot with Hinglish intelligence, Group Management, Sudoers system, and Dual-Layer Redis + MongoDB Cloud Storage.

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/ITZ-HAKEEB/MIKOBOT)

---

## 🚀 Features

- **💎 Economy & Powers**: Baka gems, $/₹ conversion, daily cash, wallet, ranking, rob, kill, protect, and powers (`rampage`, `cloak`, `vault`).
- **🎮 Mini-Games**: Card, Bomb, Hack, Roulette, Bluff with coin & gem bets.
- **🌸 AI DM Chatbot**: Powered by OpenRouter free models with real-world Indian Standard Time (IST) awareness, casual Hinglish chatting persona, and cute WebP sticker reactions.
- **🛡️ Group Management**: Admin actions (`.ban`, `.mute`, `.warn`, `.promote`, `.demote`, `.title`, `.res`, `.pin`, `.d`).
- **📢 Broadcast System**: High-speed broadcast (`/broadcast`, `/gcast`) with `-copy`, `-user`, and `-nochat` flags, flood wait handling, and dead-chat auto cleanup.
- **👑 Sudoers System**: Dynamic `/addsudo`, `/delsudo`, `/sudolist` with persistent dual-layer DB storage.
- **⚡ High Performance**: In-memory Redis caching with MongoDB persistent cloud synchronization.

---

## 🛠️ Deploy to Heroku

### Option 1: One-Click Deploy Button
Click the **Deploy to Heroku** button above or open:
[https://heroku.com/deploy?template=https://github.com/nishkarshk212/Miko](https://heroku.com/deploy?template=https://github.com/ITZ-HAKEEB/MIKOBOT)

### Option 2: Heroku CLI / Teams Deploy
```bash
# 1. Login to Heroku
heroku login

# 2. Create or connect to your Heroku app
heroku git:remote -a <YOUR_HEROKU_APP_NAME>

# 3. Set Config Vars
heroku config:set BOT_TOKEN="<YOUR_BOT_TOKEN>"
heroku config:set OWNER_ID="7408854697"
heroku config:set OPENROUTER_API_KEY="<YOUR_OPENROUTER_KEY>"
heroku config:set REDIS_URL="<YOUR_REDIS_URL>"
heroku config:set MONGO_URL="<YOUR_MONGO_URL>"

# 4. Deploy code
git push heroku main

# 5. Start the worker dyno
heroku ps:scale worker=1
```
