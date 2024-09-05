import discord
from discord.ext import commands, tasks
import asyncio
import httpx
from config import TOKEN, BACKEND_URL, GUILD_ID, NOTIFICATIONS_CHANNEL_ID
import signal
import sys
from datetime import datetime, timedelta
from discord import Embed

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

start_time = datetime.utcnow()

last_server_status = None

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.load_extension('cogs.map_data')
    await bot.load_extension('cogs.notifications')
    update_channel_description.start()
    update_bot_status.start()
    check_server_status.start()  # Start the new task

@tasks.loop(minutes=5)
async def update_channel_description():
    guild = bot.get_guild(GUILD_ID)
    if guild:
        channel = guild.get_channel(NOTIFICATIONS_CHANNEL_ID)
        if channel:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_URL}/api/map-data")
                data = response.json()
                active_players = data['active_players_count']
                total_players = data['total_players']
                uptime = get_uptime()
                await channel.edit(topic=f"Active Players: {active_players}/{total_players} | Server Uptime: {uptime}")

@tasks.loop(minutes=1)
async def update_bot_status():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/api/map-data", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                active_players = data['active_players_count']
                total_players = data['total_players']
                status = f"{active_players}/{total_players} players"
            else:
                status = "Server Offline"
    except Exception as e:
        print(f"Error updating bot status: {e}")
        status = "Server Offline"
    
    await bot.change_presence(activity=discord.Game(name=status))

@tasks.loop(minutes=1)
async def check_server_status():
    global last_server_status
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    channel = guild.get_channel(NOTIFICATIONS_CHANNEL_ID)
    if not channel:
        return

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/api/map-data", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                active_players = data['active_players_count']
                total_players = data['total_players']
                new_status = "online"
                status_message = f"🟢 Server Online | {active_players}/{total_players} players"
                color = discord.Color.green()
            else:
                new_status = "offline"
                status_message = "🔴 Server Offline"
                color = discord.Color.red()
    except Exception as e:
        print(f"Error checking server status: {e}")
        new_status = "offline"
        status_message = "🔴 Server Offline"
        color = discord.Color.red()
    
    if new_status != last_server_status:
        embed = Embed(title="Server Status Update", description=status_message, color=color)
        await channel.send(embed=embed)
        last_server_status = new_status

def get_uptime():
    now = datetime.utcnow()
    delta = now - start_time
    days, hours, minutes = delta.days, delta.seconds // 3600, (delta.seconds // 60) % 60
    return f"{days}d {hours}h {minutes}m"

@bot.command(name='w')
async def website(ctx):
    await ctx.send("Visit our website: https://website.missilewars.dev")

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    max_amount = 1000  # Set your desired maximum here
    if amount <= 0:
        await ctx.send("Please specify a positive number of messages to delete.")
        return
    if amount > max_amount:
        await ctx.send(f"You can only delete up to {max_amount} messages at once.")
        return

    # Delete command message
    await ctx.message.delete()

    deleted = 0
    batch_size = 100  # Discord allows up to 100 messages to be deleted at once
    
    # Send an initial status message
    status_message = await ctx.send(f"Deleting messages... (0/{amount})")

    try:
        while deleted < amount:
            # Calculate how many messages to delete in this batch
            to_delete = min(batch_size, amount - deleted)
            
            # Fetch and delete messages
            messages = await ctx.channel.history(limit=to_delete).flatten()
            await ctx.channel.delete_messages(messages)
            
            deleted += len(messages)
            
            # Update status message every 5 batches or when done
            if deleted % (batch_size * 5) == 0 or deleted == amount:
                await status_message.edit(content=f"Deleting messages... ({deleted}/{amount})")
            
            # Pause to respect rate limits
            await asyncio.sleep(1.5)

        # Final update and cleanup
        await status_message.edit(content=f"Deleted {deleted} messages.")
        await asyncio.sleep(5)
        await status_message.delete()

    except discord.Forbidden:
        await ctx.send("I don't have the required permissions to delete messages.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while deleting messages: {e}")

async def main():
    async with bot:
        await bot.start(TOKEN)

def signal_handler(sig, frame):
    print('Shutting down gracefully...')
    asyncio.create_task(bot.close())
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Received interrupt, shutting down...')
    finally:
        # Ensure that the bot is properly closed
        if not bot.is_closed():
            asyncio.run(bot.close())