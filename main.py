
import os
import discord
from discord.ext import commands
import json
from typing import Dict

# Initialize bot with command prefix and intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Store balances (in a real application, use a database)
balances: Dict[str, float] = {}


ADMIN_ID = "1107732198221680760"
LOG_CHANNEL_ID = "1348308761470828596"

PAYMENT_METHODS = ["In-game", "Vanguard", "Volt", "Voyager"]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def deposit(ctx, amount: float, method: str, in_game_name: str):
    if method not in PAYMENT_METHODS:
        await ctx.send(f"Invalid payment method. Please choose from: {', '.join(PAYMENT_METHODS)}")
        return

    if not ctx.message.attachments:
        await ctx.send("Please attach a screenshot of your deposit.")
        return

    screenshot = ctx.message.attachments[0]
    
    # Send request to logs channel
    log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
    
    embed = discord.Embed(title="Deposit Request", color=discord.Color.blue())
    embed.add_field(name="Amount", value=f"${amount:.2f}", inline=True)
    embed.add_field(name="Method", value=method, inline=True)
    embed.add_field(name="In-game Name", value=in_game_name, inline=True)
    embed.add_field(name="User", value=ctx.author.mention, inline=True)
    embed.set_image(url=screenshot.url)

    log_message = await log_channel.send(
        content=f"<@{ADMIN_ID}> New deposit request!",
        embed=embed,
        components=[
            discord.ui.Button(style=discord.ButtonStyle.green, label="Accept", custom_id="accept_deposit"),
            discord.ui.Button(style=discord.ButtonStyle.red, label="Deny", custom_id="deny_deposit")
        ]
    )

    # DM the user
    await ctx.author.send("Your deposit request has been submitted and will be reviewed by a staff member.")
    await ctx.message.delete()

@bot.command()
@discord.option("method", choices=PAYMENT_METHODS)
async def withdraw(ctx, amount: float, method: str, in_game_name: str):

    user_balance = balances.get(str(ctx.author.id), 0)
    if user_balance < amount:
        await ctx.send("Insufficient balance for withdrawal.")
        return

    # Send request to logs channel
    log_channel = bot.get_channel(int(LOG_CHANNEL_ID))
    
    embed = discord.Embed(title="Withdrawal Request", color=discord.Color.red())
    embed.add_field(name="Amount", value=f"${amount:.2f}", inline=True)
    embed.add_field(name="Method", value=method, inline=True)
    embed.add_field(name="In-game Name", value=in_game_name, inline=True)
    embed.add_field(name="User", value=ctx.author.mention, inline=True)

    await log_channel.send(
        content=f"<@{ADMIN_ID}> New withdrawal request!",
        embed=embed,
        components=[
            discord.ui.Button(style=discord.ButtonStyle.green, label="Accept", custom_id="accept_withdraw"),
            discord.ui.Button(style=discord.ButtonStyle.red, label="Deny", custom_id="deny_withdraw")
        ]
    )

    # DM luca
    await ctx.author.send("Your withdrawal request has been submitted and will be reviewed by a staff member.")
    await ctx.message.delete()

@bot.event
async def on_button_click(interaction: discord.Interaction):
    if not interaction.user.id == int(ADMIN_ID):
        await interaction.response.send_message("You are not authorized to perform this action.", ephemeral=True)
        return

    custom_id = interaction.custom_id
    message = interaction.message
    embed = message.embeds[0]
    user_id = embed.fields[3].value[2:-1]  # Extract user ID from mention
    amount = float(embed.fields[0].value[1:])  # Extract amount
    user = await bot.fetch_user(int(user_id))

    if custom_id in ["accept_deposit", "accept_withdraw"]:
        if custom_id == "accept_deposit":
            balances[user_id] = balances.get(user_id, 0) + amount
            await user.send(f"Your deposit of ${amount:.2f} has been approved!")
        else:
            balances[user_id] = balances.get(user_id, 0) - amount
            await user.send(f"Your withdrawal of ${amount:.2f} has been approved!")
        
        await message.edit(components=[])
        await interaction.response.send_message("Request approved!", ephemeral=True)
    
    elif custom_id in ["deny_deposit", "deny_withdraw"]:
        action = "deposit" if custom_id == "deny_deposit" else "withdrawal"
        await user.send(f"Your {action} request of ${amount:.2f} has been denied.")
        await message.edit(components=[])
        await interaction.response.send_message("Request denied!", ephemeral=True)

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
