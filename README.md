# Mac Mini Telegram Control Bot

Version: **5.0.0**

## Main features

### Security

- Private-chat-only restriction
- Admin-only access using numeric Telegram IDs
- Keyboard-only interface
- Rate limiting
- Emergency disable switches
- Alert cooldown
- Quiet hours
- Audit log
- Rejected/unauthorized access log
- No custom shell command input

### System controls

- Lock Mac
- Sleep Mac
- Display sleep
- Restart Mac
- Shutdown Mac
- Restart bot service only

Dangerous actions require confirmation.

### Monitoring

- Quick status
- Local IP
- Public IP
- CPU/RAM usage
- Top CPU apps
- Top RAM apps
- Active app/window
- Running GUI apps
- Screenshot capture
- Network speed
- Wi-Fi/Ethernet details
- Internet test
- Trash size
- Bot health
- Bot config view
- Service status
- Last 50 logs

### Disk/storage features

- Storage details
- All mounted disks/volumes:
  - device
  - mount path
  - filesystem
  - mount options
  - total space
  - used space
  - free space
  - usage percentage
- Disk health:
  - uses built-in `diskutil`
  - shows SMART status where macOS exposes it
  - optionally uses `smartctl` if installed
- Disk alert status
- Low disk alerts
- External drive mounted/unmounted alerts

### Alerts

- High CPU alert
- High RAM alert
- Low disk alert
- Public IP change alert
- Internet restored alert
- Drive mounted/unmounted alert
- Lock/unlock alert
- Login/logout alert
- Daily status report
- Bot started/restarted notification

## Install

```bash
mkdir -p ~/apps
cd ~/apps
unzip ~/Downloads/macmini_telegram_bot.zip
cd macmini_telegram_bot

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env
chmod 600 .env
```

Update `.env`:

```env
BOT_TOKEN=your_bot_token
ALLOWED_TELEGRAM_IDS=your_numeric_telegram_id
```

Run manually:

```bash
source .venv/bin/activate
python bot.py
```

Open Telegram and send:

```text
/start
```

## Install as startup service

```bash
cd ~/apps/macmini_telegram_bot
./install_launchd.sh
```

## Restart service

```bash
launchctl stop com.macmini.controlbot
launchctl start com.macmini.controlbot
```

## Check logs

```bash
tail -f ~/Library/Logs/macmini_controlbot.out.log
tail -f ~/Library/Logs/macmini_controlbot.err.log
tail -f ~/apps/macmini_telegram_bot/macmini_bot.log
```

## macOS permissions

For screenshot:

```text
System Settings > Privacy & Security > Screen Recording
```

Allow Terminal, iTerm, or whichever app starts the bot.

For active app, running apps, lock shortcut, restart, and shutdown:

```text
System Settings > Privacy & Security > Accessibility
```

Allow Terminal, iTerm, or whichever app starts the bot.

## Optional disk SMART details

The bot works with built-in `diskutil`.

For extra SMART details, install smartmontools:

```bash
brew install smartmontools
```

Then use the `🩻 Disk Health` button.
