import logging
from discord.ext import commands, tasks
import asyncio
import httpx
from config import BACKEND_URL, NOTIFICATIONS_CHANNEL_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                
                logger.info(f"Checking for missiles with params: {params}")
                response = await client.get(f"{BACKEND_URL}/api/recent-missiles", params=params)
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"Received data: {data}")

                for missile in data.get('missiles', []):
                    channel = self.bot.get_channel(NOTIFICATIONS_CHANNEL_ID)
                    if channel:
                        message = f"{missile.get('sentBy', 'Unknown')} fired a {missile.get('type', 'unknown')} missile"
                        if 'targetUsername' in missile:
                            message += f" at {missile['targetUsername']}"
                        await channel.send(message)
                    else:
                        logger.error(f"Could not find channel with ID {NOTIFICATIONS_CHANNEL_ID}")
                
                if data.get('missiles'):
                    self.last_checked_time = max(missile.get('sentAt', self.last_checked_time) for missile in data['missiles'])
                    logger.info(f"Updated last_checked_time to {self.last_checked_time}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            logger.error(f"Response content: {e.response.text}")
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)

    @check_for_missiles.before_loop
    async def before_check_for_missiles(self):
        await self.bot.wait_until_ready()

    @commands.command(name='testmissiles')
    async def test_missiles(self, ctx):
        await self.check_for_missiles()
        await ctx.send("Missile check completed. Check logs for details.")

async def setup(bot):
    await bot.add_cog(Notifications(bot))