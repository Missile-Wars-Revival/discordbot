import logging
from discord.ext import commands, tasks
import asyncio
import httpx
from config import BACKEND_URL, NOTIFICATIONS_CHANNEL_ID
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_checked_time = datetime.now(timezone.utc)
        self.notified_missile_ids = set()
        self.check_for_missiles.start()

    def cog_unload(self):
        self.check_for_missiles.cancel()

    @tasks.loop(seconds=30)  # Check every 30 seconds
    async def check_for_missiles(self):
        try:
            async with httpx.AsyncClient() as client:
                params = {'since': self.last_checked_time.isoformat()}
                
                logger.info(f"Checking for missiles with params: {params}")
                response = await client.get(f"{BACKEND_URL}/api/recent-missiles", params=params)
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"Received data: {data}")

                for missile in data.get('missiles', []):
                    missile_id = missile.get('id')
                    if missile_id and missile_id not in self.notified_missile_ids:
                        channel = self.bot.get_channel(NOTIFICATIONS_CHANNEL_ID)
                        if channel:
                            message = f"{missile.get('sentBy', 'Unknown')} fired a {missile.get('type', 'unknown')} missile"
                            if 'targetUsername' in missile:
                                message += f" at {missile['targetUsername']}"
                            await channel.send(message)
                            self.notified_missile_ids.add(missile_id)
                        else:
                            logger.error(f"Could not find channel with ID {NOTIFICATIONS_CHANNEL_ID}")
                
                if data.get('missiles'):
                    self.last_checked_time = max(
                        datetime.fromisoformat(missile.get('sentAt', self.last_checked_time.isoformat()))
                        for missile in data['missiles']
                    )
                    logger.info(f"Updated last_checked_time to {self.last_checked_time}")

                # Prune old missile IDs to prevent set from growing indefinitely
                current_time = datetime.now(timezone.utc)
                self.notified_missile_ids = {
                    missile_id for missile_id in self.notified_missile_ids
                    if (current_time - datetime.fromisoformat(data['missiles'][missile_id]['sentAt'])).total_seconds() < 3600
                }

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