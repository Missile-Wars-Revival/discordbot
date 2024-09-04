from discord.ext import commands
import httpx

class MapData(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='mapstats')
    async def map_stats(self, ctx):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.bot.BACKEND_URL}/api/map-data")
            data = response.json()
            await ctx.send(f"Active Players: {data['active_players_count']}\n"
                           f"Total Players: {data['total_players']}\n"
                           f"Active Missiles: {data['total_missiles']}")

async def setup(bot):
    await bot.add_cog(MapData(bot))