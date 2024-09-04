import discord
from discord.ext import commands, tasks
import asyncio
import httpx
from config import TOKEN, BACKEND_URL, GUILD_ID, NOTIFICATIONS_CHANNEL_ID
import signal
import sys

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.load_extension('cogs.map_data')
    await bot.load_extension('cogs.notifications')
    update_channel_description.start()
    update_bot_status.start()

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
                await channel.edit(topic=f"Active Players: {active_players}/{total_players}")

@tasks.loop(minutes=1)
async def update_bot_status():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/api/map-data")
            data = response.json()
            active_players = data['active_players_count']
            total_players = data['total_players']
            status = f"{active_players}/{total_players} players online"
            await bot.change_presence(activity=discord.Game(name=status))
    except Exception as e:
        print(f"Error updating bot status: {e}")

@bot.command(name='w')
async def website(ctx):
    await ctx.send("Visit our website: https://website.missilewars.dev")

@bot.command(name='clear')
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount <= 0:
        await ctx.send("Please specify a positive number of messages to delete.")
        return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
        await ctx.send(f"Deleted {len(deleted) - 1} messages.", delete_after=5)
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