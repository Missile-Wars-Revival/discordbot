import discord
from discord.ext import commands, tasks
import asyncio
import httpx
from config import FIREBASE_CREDENTIALS_PATH, TOKEN, BACKEND_URL, GUILD_ID, NOTIFICATIONS_CHANNEL_ID
import signal
import sys
from datetime import datetime, timedelta
from discord import Embed
import firebase_admin
from firebase_admin import credentials

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

start_time = datetime.utcnow()

last_server_status = None

# Initialize Firebase
cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred, {
    'storageBucket': 'missile-wars-revival-10.appspot.com'
})

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.load_extension('cogs.map_data')
    await bot.load_extension('cogs.notifications')
    update_channel_description.start()
    update_bot_status.start()
    check_server_status.start() 

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
            response.raise_for_status()
            content = response.text
            print(f"Raw response content: {content}")  # Log raw response
            if not content.strip():
                raise ValueError("Empty response")
            data = response.json()
            active_players = data['active_players_count']
            total_players = data['total_players']
            status = f"{active_players}/{total_players} players"
    except httpx.HTTPStatusError as e:
        print(f"Error updating bot status: HTTP {e.response.status_code}")
        print(f"Response content: {e.response.text}")
        status = "Server Error"
    except httpx.RequestError as e:
        print(f"Error updating bot status: {str(e)}")
        status = "Connection Error"
    except ValueError as e:
        print(f"Error updating bot status: {str(e)}")
        print(f"Response content: {response.text if 'response' in locals() else 'No response'}")
        status = "Data Error"
    except Exception as e:
        print(f"Error updating bot status: {str(e)}")
        status = "Unknown Error"
    
    print(f"Setting bot status to: {status}")  # Log the status being set
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
    max_amount = 1000  # Maximum number of messages to delete
    if amount <= 0:
        await ctx.send("Please specify a positive number of messages to delete.")
        return
    if amount > max_amount:
        await ctx.send(f"You can only delete up to {max_amount} messages at once.")
        return

    # Delete command message
    await ctx.message.delete()

    deleted = 0
    
    # Send an initial status message
    status_message = await ctx.send(f"Deleting messages... (0/{amount})")

    try:
        while deleted < amount:
            # Delete messages in chunks of 100 (Discord's limit)
            to_delete = min(100, amount - deleted)
            deleted += to_delete
            await ctx.channel.purge(limit=to_delete)
            
            # Update status message every 200 deletions or when done
            if deleted % 200 == 0 or deleted == amount:
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