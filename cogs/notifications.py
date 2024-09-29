import logging
from discord.ext import commands, tasks
import httpx
import discord
import firebase_admin
from firebase_admin import storage
from config import BACKEND_URL, NOTIFICATIONS_CHANNEL_ID, FIREBASE_CREDENTIALS_PATH
from datetime import datetime, timezone
import time  # Add this import
from datetime import timedelta  # Add this import

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_checked_time = datetime.now(timezone.utc)
        self.notified_ids = set()
        self.check_for_updates.start()
        self.bucket = storage.bucket()  # This gets the default Firebase Storage bucket

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
                await self.process_other(data.get('other', []))

                if data.get('missiles') or data.get('landmines') or data.get('other'):
                    self.last_checked_time = max(
                        datetime.fromisoformat(item.get('sentAt', self.last_checked_time.isoformat()))
                        for item in data.get('missiles', []) + data.get('landmines', []) + data.get('other', [])
                    )
                    logger.info(f"Updated last_checked_time to {self.last_checked_time}")

                # Prune old notified IDs
                self.prune_notified_ids(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            logger.error(f"Response content: {e.response.text}")
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)

    async def process_items(self, items, item_type):
        for item in items:
            item_id = item.get('id')
            if item_id and item_id not in self.notified_ids:
                if item_type == "missile":
                    action = "fired a"
                    actor = item.get('sentBy', 'Unknown')
                else:
                    action = "placed a"
                    actor = item.get('placedBy', 'Unknown')
                
                target = f" at {item['targetUsername']}" if 'targetUsername' in item else f" in {item['location']}" if 'location' in item else ""
                await self.send_notification(
                    f"{actor} {action} {item.get('type', item_type)}",
                    target,
                    actor
                )
                self.notified_ids.add(item_id)

    async def process_missiles(self, missiles):
        await self.process_items(missiles, "missile")

    async def process_landmines(self, landmines):
        await self.process_items(landmines, "landmine")
    
    async def process_other(self, other):
        await self.process_items(other, "other")

    async def send_notification(self, title, description, username):
        channel = self.bot.get_channel(NOTIFICATIONS_CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID {NOTIFICATIONS_CHANNEL_ID}")
            return

        embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        
        try:
            blob = self.bucket.blob(f"profileImages/{username}")
            
            # Use run_in_executor for the blob.exists() check
            exists = await self.bot.loop.run_in_executor(None, blob.exists)
            logger.info(f"Profile image for {username} exists: {exists}")
            
            if exists:
                # Calculate the expiration time as a Unix timestamp
                expiration_time = int(time.time() + 3600)  # 1 hour from now
                logger.info(f"Setting signed URL expiration time to {expiration_time} (Unix timestamp)")
                
                url = await self.bot.loop.run_in_executor(
                    None, 
                    lambda: blob.generate_signed_url(expiration=expiration_time)
                )
                logger.info(f"Generated signed URL for {username}: {url}")
                embed.set_thumbnail(url=url)
            else:
                logger.warning(f"Profile image for {username} not found")
        except Exception as e:
            logger.error(f"Error fetching profile image for {username}: {e}", exc_info=True)

        try:
            await channel.send(embed=embed)
            logger.info(f"Sent notification for {username}")
        except discord.errors.HTTPException as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)

    def prune_notified_ids(self, data):
        current_time = datetime.now(timezone.utc)
        all_items = data.get('missiles', []) + data.get('landmines', []) + data.get('other', [])
        valid_ids = set()

        for item in all_items:
            item_id = item.get('id')
            if item_id is None:
                continue

            if 'sentAt' in item:  # For missiles
                expiration_time = datetime.fromisoformat(item['sentAt']) + timedelta(hours=1)
            elif 'Expires' in item:  # For landmines and other
                expiration_time = datetime.fromisoformat(item['Expires'])
            else:
                continue  # Skip items without a valid expiration time

            if current_time < expiration_time:
                valid_ids.add(item_id)

        self.notified_ids.intersection_update(valid_ids)

    @check_for_updates.before_loop
    async def before_check_for_updates(self):
        await self.bot.wait_until_ready()

    @commands.command(name='testupdates')
    async def test_updates(self, ctx):
        await self.check_for_updates()
        await ctx.send("Update check completed. Check logs for details.")

async def setup(bot):
    await bot.add_cog(Notifications(bot))