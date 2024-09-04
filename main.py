import discord
from discord.ext import commands, tasks
import asyncio
import httpx
from config import TOKEN, BACKEND_URL, GUILD_ID, CHANNEL_ID

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.load_extension('cogs.map_data')
    await bot.load_extension('cogs.notifications')
    update_channel_description.start()

@tasks.loop(minutes=5)
async def update_channel_description():
    guild = bot.get_guild(GUILD_ID)
    if guild:
        channel = guild.get_channel(CHANNEL_ID)
        if channel:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_URL}/api/map-data")
                data = response.json()
                active_players = data['active_players_count']
                total_players = data['total_players']
                await channel.edit(topic=f"Active Players: {active_players}/{total_players}")

@bot.command(name='w')
async def website(ctx):
    await ctx.send("Visit our website: https://website.missilewars.dev")

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())