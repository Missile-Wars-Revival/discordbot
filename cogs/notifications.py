from discord.ext import commands, tasks
import asyncio
import httpx
from config import BACKEND_URL, NOTIFICATIONS_CHANNEL_ID

class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_checked_time = None
        self.check_for_missiles.start()

    def cog_unload(self):
        self.check_for_missiles.cancel()

    @tasks.loop(seconds=30)  # Check every 30 seconds
    async def check_for_missiles(self):
        try:
            async with httpx.AsyncClient() as client:
                params = {}
                if self.last_checked_time:
                    params['since'] = self.last_checked_time.isoformat()
                
                response = await client.get(f"{BACKEND_URL}/api/recent-missiles", params=params)
                response.raise_for_status()
                data = response.json()

                for missile in data['missiles']:
                    channel = self.bot.get_channel(NOTIFICATIONS_CHANNEL_ID)
                    await channel.send(f"{missile['sentBy']} fired a {missile['type']} missile at {missile['targetUsername']}!")
                
                if data['missiles']:
                    self.last_checked_time = max(missile['sentAt'] for missile in data['missiles'])

        except httpx.HTTPError as e:
            print(f"HTTP error occurred: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

    @check_for_missiles.before_loop
    async def before_check_for_missiles(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Notifications(bot))