import os
import discord
from discord.ext import commands
import sqlite3
from typing import Dict
import random

# Initialize database
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY,
                  balance REAL DEFAULT 0.0,
                  in_game_name TEXT,
                  discord_name TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Initialize bot with command prefix and intents
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix='/',
    intents=intents,
    application_id=os.getenv("APPLICATION_ID")
)

# Store pending transfers
pending_transfers = {}

def generate_transfer_id():
    return str(random.randint(1000, 9999))

ADMIN_IDS = ["1107732198221680760", "1314310123421831198"]  # List of admin IDs
LOG_CHANNEL_ID = "1348308761470828596"
REQUESTS_CHANNEL_ID = "1348308761470828596"  # Channel where deposit/withdraw requests are allowed

PAYMENT_METHODS = ["In-game", "Vanguard", "Volt", "Voyager"]

def is_requests_channel(channel_id: str) -> bool:
    return str(channel_id) == REQUESTS_CHANNEL_ID

@bot.tree.command(description="Deposit funds with proof")
@discord.app_commands.describe(
    amount="Amount to deposit",
    method="Payment method",
    in_game_name="Your in-game name",
    proof="Screenshot of your deposit"
)
async def deposit(interaction: discord.Interaction, amount: float, method: str, in_game_name: str, proof: discord.Attachment):
    # Defer immediately to prevent timeout
    await interaction.response.defer(ephemeral=True)

    if method not in PAYMENT_METHODS:
        await interaction.followup.send(f"Invalid payment method. Please choose from: {', '.join(PAYMENT_METHODS)}", ephemeral=True)
        return

    # Update user data with in-game name and Discord name
    user_data = get_user_data(str(interaction.user.id))
    user_data["in_game_name"] = in_game_name
    user_data["discord_name"] = str(interaction.user)
    save_user_data(str(interaction.user.id), user_data)

    screenshot = proof
    transfer_id = generate_transfer_id()
    
    # Send request to logs channel
    log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
    if not log_channel:
        await interaction.followup.send("Error: Could not find logging channel. Please contact an administrator.", ephemeral=True)
        return
    
    embed = discord.Embed(title="Deposit Request", color=discord.Color.blue())
    embed.add_field(name="Transfer ID", value=transfer_id, inline=True)
    embed.add_field(name="Amount", value=f"${amount:.2f}", inline=True)
    embed.add_field(name="Method", value=method, inline=True)
    embed.add_field(name="In-game Name", value=in_game_name, inline=True)
    embed.add_field(name="User", value=interaction.user.mention, inline=True)
    embed.set_image(url=screenshot.url)

    # Store transfer details
    pending_transfers[transfer_id] = {
        "type": "deposit",
        "user_id": str(interaction.user.id),
        "amount": amount,
        "message_id": None
    }

    message = await log_channel.send(
        content="@Admin New deposit request!",
        embed=embed
    )
    
    # Store message ID
    pending_transfers[transfer_id]["message_id"] = message.id

    # DM the user
    await interaction.user.send(f"Your deposit request has been submitted. Transfer ID: {transfer_id}")
    await interaction.followup.send(f"Your deposit request has been submitted successfully! Transfer ID: {transfer_id}", ephemeral=True)

@bot.tree.command(description="Withdraw funds")
async def withdraw(interaction: discord.Interaction, amount: float, method: str, in_game_name: str):
    # Check if command is used in the correct channel
    if not is_requests_channel(str(interaction.channel_id)):
        await interaction.response.send_message("This command can only be used in the deposit/withdrawal requests channel.", ephemeral=True)
        return

    # Defer immediately to prevent timeout
    await interaction.response.defer(ephemeral=True)

    if method not in PAYMENT_METHODS:
        await interaction.followup.send(f"Invalid payment method. Please choose from: {', '.join(PAYMENT_METHODS)}", ephemeral=True)
        return

    # Update user data with in-game name and Discord name
    user_data = get_user_data(str(interaction.user.id))
    user_data["in_game_name"] = in_game_name
    user_data["discord_name"] = str(interaction.user)
    save_user_data(str(interaction.user.id), user_data)

    user_balance = user_data["balance"]
    if user_balance < amount:
        await interaction.followup.send("Insufficient balance for withdrawal.", ephemeral=True)
        return

    transfer_id = generate_transfer_id()
    
    # Send request to logs channel
    log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
    
    embed = discord.Embed(title="Withdrawal Request", color=discord.Color.red())
    embed.add_field(name="Transfer ID", value=transfer_id, inline=True)
    embed.add_field(name="Amount", value=f"${amount:.2f}", inline=True)
    embed.add_field(name="Method", value=method, inline=True)
    embed.add_field(name="In-game Name", value=in_game_name, inline=True)
    embed.add_field(name="User", value=interaction.user.mention, inline=True)

    # Store transfer details
    pending_transfers[transfer_id] = {
        "type": "withdraw",
        "user_id": str(interaction.user.id),
        "amount": amount,
        "message_id": None
    }

    message = await log_channel.send(
        content="@Admin New withdrawal request!",
        embed=embed
    )
    
    # Store message ID
    pending_transfers[transfer_id]["message_id"] = message.id

    # DM the user
    await interaction.user.send(f"Your withdrawal request has been submitted. Transfer ID: {transfer_id}")
    await interaction.followup.send(f"Your withdrawal request has been submitted successfully! Transfer ID: {transfer_id}", ephemeral=True)

@bot.tree.command(description="Accept a transfer request")
@discord.app_commands.describe(
    transfer_id="The ID of the transfer to accept"
)
async def accept(interaction: discord.Interaction, transfer_id: str):
    # Check if command is used in the correct channel
    if not is_requests_channel(str(interaction.channel_id)):
        await interaction.response.send_message("This command can only be used in the deposit/withdrawal requests channel.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if transfer_id not in pending_transfers:
        await interaction.followup.send("Invalid transfer ID.", ephemeral=True)
        return

    transfer = pending_transfers[transfer_id]
    user = await bot.fetch_user(int(transfer["user_id"]))
    
    try:
        user_data = get_user_data(transfer["user_id"])
        if transfer["type"] == "deposit":
            user_data["balance"] += transfer["amount"]
            await user.send(f"Your deposit of ${transfer['amount']:.2f} has been approved by {interaction.user.name}!")
        else:
            user_data["balance"] -= transfer["amount"]
            await user.send(f"Your withdrawal of ${transfer['amount']:.2f} has been approved by {interaction.user.name}!")
        
        save_user_data(transfer["user_id"], user_data)
        
        # Update the original message
        log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
        message = await log_channel.fetch_message(transfer["message_id"])
        embed = message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="Status", value=f"Approved by {interaction.user.name}", inline=False)
        await message.edit(embed=embed)
        
        # Remove from pending transfers
        del pending_transfers[transfer_id]
        
        await interaction.followup.send("Transfer approved successfully!", ephemeral=True)
    except Exception as e:
        print(f"Error in accept command: {e}")
        await interaction.followup.send("An error occurred while processing the transfer.", ephemeral=True)

@bot.tree.command(description="Deny a transfer request")
@discord.app_commands.describe(
    transfer_id="The ID of the transfer to deny"
)
async def deny(interaction: discord.Interaction, transfer_id: str):
    # Check if command is used in the correct channel
    if not is_requests_channel(str(interaction.channel_id)):
        await interaction.response.send_message("This command can only be used in the deposit/withdrawal requests channel.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if transfer_id not in pending_transfers:
        await interaction.followup.send("Invalid transfer ID.", ephemeral=True)
        return

    transfer = pending_transfers[transfer_id]
    user = await bot.fetch_user(int(transfer["user_id"]))
    
    try:
        action = "deposit" if transfer["type"] == "deposit" else "withdrawal"
        await user.send(f"Your {action} request of ${transfer['amount']:.2f} has been denied by {interaction.user.name}.")
        
        # Update the original message
        log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
        message = await log_channel.fetch_message(transfer["message_id"])
        embed = message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="Status", value=f"Denied by {interaction.user.name}", inline=False)
        await message.edit(embed=embed)
        
        # Remove from pending transfers
        del pending_transfers[transfer_id]
        
        await interaction.followup.send("Transfer denied successfully!", ephemeral=True)
    except Exception as e:
        print(f"Error in deny command: {e}")
        await interaction.followup.send("An error occurred while processing the transfer.", ephemeral=True)

@bot.event
async def setup_hook():
    await bot.tree.sync()

def get_user_data(user_id: str) -> Dict:
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    
    if row is None:
        # Create new user if they don't exist
        default_data = {"balance": 0.0, "in_game_name": "", "discord_name": ""}
        save_user_data(user_id, default_data)
        return default_data
    
    return {
        "balance": row[1],
        "in_game_name": row[2] or "",
        "discord_name": row[3] or ""
    }

def save_user_data(user_id: str, data: dict):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users (user_id, balance, in_game_name, discord_name)
                 VALUES (?, ?, ?, ?)''',
              (user_id, data["balance"], data.get("in_game_name", ""), data.get("discord_name", "")))
    conn.commit()
    conn.close()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='the Cashino'))

try:
    token = os.getenv("TOKEN") or ""
    if token == "":
        raise Exception("Please add your token to the Secrets pane.")
    bot.run(token)
except discord.HTTPException as e:
    if e.status == 429:
        print("The Discord servers denied the connection for making too many requests")
        print("Get help from https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests")
    else:
        raise e
