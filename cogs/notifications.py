import logging
from discord.ext import commands, tasks
import httpx
from config import BACKEND_URL, NOTIFICATIONS_CHANNEL_ID
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_checked_time = datetime.now(timezone.utc)
        self.notified_ids = set()
        self.check_for_updates.start()

    def cog_unload(self):
        self.check_for_updates.cancel()

    @tasks.loop(seconds=30)  # Check every 30 seconds
    async def check_for_updates(self):
        try:
            async with httpx.AsyncClient() as client:
                params = {'since': self.last_checked_time.isoformat()}
                
                logger.info(f"Checking for updates with params: {params}")
                response = await client.get(f"{BACKEND_URL}/api/recent-updates", params=params)
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"Received data: {data}")

                await self.process_missiles(data.get('missiles', []))
                await self.process_landmines(data.get('landmines', []))

                if data.get('missiles') or data.get('landmines'):
                    self.last_checked_time = max(
                        datetime.fromisoformat(item.get('sentAt', self.last_checked_time.isoformat()))
                        for item in data.get('missiles', []) + data.get('landmines', [])
                    )
                    logger.info(f"Updated last_checked_time to {self.last_checked_time}")

                # Prune old notified IDs
                self.prune_notified_ids(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            logger.error(f"Response content: {e.response.text}")
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)

    async def process_missiles(self, missiles):
        for missile in missiles:
            missile_id = missile.get('id')
            if missile_id and missile_id not in self.notified_ids:
                await self.send_notification(
                    f"{missile.get('sentBy', 'Unknown')} fired a {missile.get('type', 'unknown')} missile"
                    f"{' at ' + missile['targetUsername'] if 'targetUsername' in missile else ''}"
                )
                self.notified_ids.add(missile_id)

    async def process_landmines(self, landmines):
        for landmine in landmines:
            landmine_id = landmine.get('id')
            if landmine_id and landmine_id not in self.notified_ids:
                await self.send_notification(
                    f"{landmine.get('placedBy', 'Unknown')} placed a landmine"
                    f"{' in ' + landmine['location'] if 'location' in landmine else ''}"
                )
                self.notified_ids.add(landmine_id)

    async def send_notification(self, message):
        channel = self.bot.get_channel(NOTIFICATIONS_CHANNEL_ID)
        if channel:
            await channel.send(message)
        else:
            logger.error(f"Could not find channel with ID {NOTIFICATIONS_CHANNEL_ID}")

    def prune_notified_ids(self, data):
        current_time = datetime.now(timezone.utc)
        self.notified_ids = {
            item_id for item_id in self.notified_ids
            if any(
                (current_time - datetime.fromisoformat(item.get('sentAt', ''))).total_seconds() < 3600
                for item in data.get('missiles', []) + data.get('landmines', [])
                if item.get('id') == item_id
            )
        }

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()

    @commands.command(name='testupdates')
    async def test_updates(self, ctx):
        await self.check_for_updates()
        await ctx.send("Update check completed. Check logs for details.")

async def setup(bot):
    await bot.add_cog(Notifications(bot))