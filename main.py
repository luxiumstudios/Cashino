import os
import discord
from discord.ext import commands
import sqlite3
from typing import Dict

# Initialize database
def init_db():
    # Mock init - do nothing
    pass

init_db()

# Initialize bot with command prefix and intents
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix='/',
    intents=intents,
    application_id=os.getenv("APPLICATION_ID")
)

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

    screenshot = proof
    
    # Send request to logs channel
    log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
    if not log_channel:
        await interaction.followup.send("Error: Could not find logging channel. Please contact an administrator.", ephemeral=True)
        return
    
    embed = discord.Embed(title="Deposit Request", color=discord.Color.blue())
    embed.add_field(name="Amount", value=f"${amount:.2f}", inline=True)
    embed.add_field(name="Method", value=method, inline=True)
    embed.add_field(name="In-game Name", value=in_game_name, inline=True)
    embed.add_field(name="User", value=interaction.user.mention, inline=True)
    embed.set_image(url=screenshot.url)

    view = discord.ui.View()
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="Accept", custom_id="accept_deposit"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.red, label="Deny", custom_id="deny_deposit"))

    await log_channel.send(
        content="@Admin New deposit request!",
        embed=embed,
        view=view
    )

    # DM the user
    await interaction.user.send("Your deposit request has been submitted and will be reviewed by a staff member.")
    await interaction.followup.send("Your deposit request has been submitted successfully!", ephemeral=True)

@bot.tree.command(description="Withdraw funds")
async def withdraw(interaction: discord.Interaction, amount: float, method: str, in_game_name: str):
    # Defer immediately to prevent timeout
    await interaction.response.defer(ephemeral=True)

    if method not in PAYMENT_METHODS:
        await interaction.followup.send(f"Invalid payment method. Please choose from: {', '.join(PAYMENT_METHODS)}", ephemeral=True)
        return

    user_balance = get_user_data(str(interaction.user.id))["balance"]
    if user_balance < amount:
        await interaction.followup.send("Insufficient balance for withdrawal.", ephemeral=True)
        return

    # Send request to logs channel
    log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
    
    embed = discord.Embed(title="Withdrawal Request", color=discord.Color.red())
    embed.add_field(name="Amount", value=f"${amount:.2f}", inline=True)
    embed.add_field(name="Method", value=method, inline=True)
    embed.add_field(name="In-game Name", value=in_game_name, inline=True)
    embed.add_field(name="User", value=interaction.user.mention, inline=True)

    view = discord.ui.View()
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="Accept", custom_id="accept_withdraw"))
    view.add_item(discord.ui.Button(style=discord.ButtonStyle.red, label="Deny", custom_id="deny_withdraw"))

    await log_channel.send(
        content="@Admin New withdrawal request!",
        embed=embed,
        view=view
    )

    # DM the user
    await interaction.user.send("Your withdrawal request has been submitted and will be reviewed by a staff member.")
    await interaction.followup.send("Your withdrawal request has been submitted successfully!", ephemeral=True)

@bot.event
async def setup_hook():
    await bot.tree.sync()

def get_user_data(user_id: str):
    # Mock data for testing
    return {"balance": 1000.0, "in_game_name": "TestUser", "discord_name": "TestUser#1234"}

def save_user_data(user_id: str, data: dict):
    # Mock save - do nothing
    pass

ADMIN_IDS = ["1107732198221680760", "1314310123421831198"]  # List of admin IDs
LOG_CHANNEL_ID = "1348308761470828596"

PAYMENT_METHODS = ["In-game", "Vanguard", "Volt", "Voyager"]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='the Cashino'))

@bot.event
async def on_button_click(interaction: discord.Interaction):
    try:
        # Defer immediately to prevent timeout
        await interaction.response.defer(ephemeral=True)

        custom_id = interaction.custom_id
        message = interaction.message
        embed = message.embeds[0]
        user_id = embed.fields[3].value[2:-1]  # Extract user ID from mention
        amount = float(embed.fields[0].value[1:])  # Extract amount
        user = await bot.fetch_user(int(user_id))
        
        if custom_id in ["accept_deposit", "accept_withdraw"]:
            user_data = get_user_data(user_id)
            if custom_id == "accept_deposit":
                user_data["balance"] += amount
                await user.send(f"Your deposit of ${amount:.2f} has been approved by {interaction.user.name}!")
            else:
                user_data["balance"] -= amount
                await user.send(f"Your withdrawal of ${amount:.2f} has been approved by {interaction.user.name}!")
            save_user_data(user_id, user_data)
            await message.edit(view=None)
            await interaction.followup.send("Request approved!", ephemeral=True)
        else:
            action = "deposit" if custom_id == "deny_deposit" else "withdrawal"
            await user.send(f"Your {action} request of ${amount:.2f} has been denied by {interaction.user.name}.")
            await message.edit(view=None)
            await interaction.followup.send("Request denied!", ephemeral=True)

    except Exception as e:
        print(f"Error in on_button_click: {e}")
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)
        except:
            print(f"Failed to send error message: {e}")

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
