# Mac Mini Telegram Bot Testing Guide

Use this checklist after installing or updating the bot.

## 1. Basic startup test

Run manually first:

```bash
cd ~/apps/macmini_telegram_bot
source .venv/bin/activate
python bot.py
```

Expected:

- No Python error
- Bot sends a startup message to the allowed admin Telegram ID
- `/start` shows the keyboard

## 2. Admin allow-list test

Send `/start` from your allowed Telegram account.

Expected:

- Bot shows the keyboard

Send `/start` from another Telegram account not in `ALLOWED_TELEGRAM_IDS`.

Expected:

- Bot replies with access denied
- Rejected attempt is logged in `unauthorized_access_log.jsonl`

## 3. Private-chat-only test

Add the bot to a Telegram group and send `/start`.

Expected:

- Bot rejects the request
- It says the bot only works in private chat
- Rejected attempt is logged

Recommended: remove the bot from the group after testing.

## 4. Main keyboard test

Press:

- `⚡ Quick Status`
- `🏠 Local IP`
- `🖥 System`
- `💾 Storage`
- `🌐 Network`
- `🛠 Controls`
- `📜 Logs`

Expected:

- Each menu opens
- `⬅️ Back` returns to the main menu

## 5. Disk and storage test

Go to `💾 Storage`.

Test:

### `💾 Storage Details`

Expected:

- Shows root disk
- Shows `/Volumes/...` mounted drives if available

### `🗂 All Mounted Disks`

Expected:

For each mounted disk/volume, it should show:

- Mount path
- Device
- Filesystem
- Options
- Total
- Used
- Free
- Usage percentage

### `🩻 Disk Health`

Expected:

- Shows diskutil health/SMART info if available
- If `smartctl` is not installed, it should say:
  `smartctl: Not installed. Optional: brew install smartmontools`

Optional:

```bash
brew install smartmontools
```

Then test `🩻 Disk Health` again.

### External drive mounted/unmounted alert

1. Start the bot
2. Connect a USB/external drive
3. Wait up to `ALERT_CHECK_INTERVAL_SECONDS`
4. Unmount/eject the drive
5. Wait again

Expected:

- Bot sends drive mounted alert
- Bot sends drive unmounted alert

## 6. Screenshot test

Go to `🖥 System` > `📸 Screenshot`.

Expected:

- Bot sends a screenshot file

If it fails:

Open:

```text
System Settings > Privacy & Security > Screen Recording
```

Allow the terminal app that starts the bot.

Then restart the bot and test again.

## 7. Active app/running apps test

Go to `🖥 System`.

Test:

- `🪟 Active App`
- `📋 Running Apps`

Expected:

- Active app/window is shown
- Running GUI apps are listed

If it fails:

Open:

```text
System Settings > Privacy & Security > Accessibility
```

Allow the terminal app that starts the bot.

Then restart the bot and test again.

## 8. Lock feature test

Press:

```text
🔒 Lock Mac
✅ Confirm Lock
```

Expected:

- Mac locks or display sleeps
- Bot logs the action
- Lock/unlock alert may be sent after the next alert check

## 9. Control confirmation test

Press:

- `🌙 Sleep Mac`
- `🔁 Restart Mac`
- `⏻ Shutdown Mac`

Do not confirm unless you really want the action.

Expected:

- Bot asks for confirmation
- `❌ Cancel` cancels the pending action

## 10. Rate limit test

Press `⚡ Quick Status` repeatedly more than `RATE_LIMIT_GENERAL_PER_MINUTE`.

Expected:

- Bot eventually replies with a rate limit message

Press `📸 Screenshot` more than `RATE_LIMIT_SCREENSHOT_PER_MINUTE`.

Expected:

- Screenshot rate limit message appears

## 11. Emergency disable switch test

Edit `.env`:

```env
CONTROL_ACTIONS_ENABLED=false
```

Restart the bot.

Try `🔒 Lock Mac`.

Expected:

- Bot refuses control action
- Status buttons still work

Test screenshot disable:

```env
SCREENSHOT_ENABLED=false
```

Restart and press `📸 Screenshot`.

Expected:

- Bot refuses screenshot

Test status disable:

```env
STATUS_FEATURES_ENABLED=false
```

Restart and press `⚡ Quick Status`.

Expected:

- Bot refuses status feature

## 12. Quiet hours test

Edit `.env`:

```env
QUIET_HOURS_ENABLED=true
QUIET_HOURS_START=00:00
QUIET_HOURS_END=23:59
```

Restart the bot.

Expected:

- Non-critical alerts are suppressed
- Critical alerts like high CPU/disk/login/lock can still be sent

Set it back after testing:

```env
QUIET_HOURS_ENABLED=false
```

## 13. Alert cooldown test

Edit `.env`:

```env
ALERT_COOLDOWN_MINUTES=30
```

Expected:

- Same alert type is not repeatedly spammed within 30 minutes

## 14. Login/logout alert test

Enable:

```env
ENABLE_LOGIN_LOGOUT_ALERTS=true
```

Lock/log out or switch user.

Expected:

- Bot sends login/logout or console-user-change alert after the next alert cycle

## 15. Lock/unlock alert test

Enable:

```env
ENABLE_LOCK_UNLOCK_ALERTS=true
```

Lock and unlock the Mac.

Expected:

- Bot sends lock/unlock alert after the next alert cycle

Note:

Some macOS versions may not expose lock state through `ioreg`. In that case the bot shows `unknown` and does not send lock/unlock alerts.

## 16. Last 50 logs test

Go to:

```text
📜 Logs > 📄 Last 50 Logs
```

Expected:

- Bot sends recent log lines

## 17. Bot config test

Go to:

```text
🖥 System > ⚙️ Bot Config
```

Expected:

- Shows safe config values
- Does not show the bot token

## 18. Export logs test

Go to:

```text
📜 Logs > 📦 Export Logs
```

Expected:

- Bot sends a ZIP file containing logs and state files

## 19. launchd service test

Install service:

```bash
cd ~/apps/macmini_telegram_bot
./install_launchd.sh
```

Check service:

```bash
launchctl list com.macmini.controlbot
```

In Telegram:

```text
🖥 System > ⚙️ Service Status
```

Expected:

- Loaded/Running: Yes

Restart service:

```bash
launchctl stop com.macmini.controlbot
launchctl start com.macmini.controlbot
```

Expected:

- Bot sends startup notification

## 20. Final production check

Before leaving it running:

```bash
chmod 600 ~/apps/macmini_telegram_bot/.env
```

Check `.env`:

- Correct `BOT_TOKEN`
- Correct `ALLOWED_TELEGRAM_IDS`
- `BOT_ENABLED=true`
- `CONTROL_ACTIONS_ENABLED=true` only if you want remote controls active
- `SCREENSHOT_ENABLED=true` only if screenshot is needed
- Quiet hours set as desired
- Rate limits set as desired

Do not add the bot to groups.
Do not share the bot token.
