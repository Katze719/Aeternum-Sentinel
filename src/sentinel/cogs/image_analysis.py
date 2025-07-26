from __future__ import annotations

import logging
import re
from typing import List, Optional
import base64

import discord
from discord import app_commands
from discord.ext import commands

import sentinel.utils.storage as storage

_log = logging.getLogger(__name__)

# Config keys
IMAGE_ANALYSIS_ENABLED_KEY = "image_analysis_enabled"
IMAGE_ANALYSIS_CHANNEL_KEY = "image_analysis_channel_id"
GEMINI_API_KEY_KEY = "gemini_api_key"

class ImageAnalysis(commands.Cog):
    """Analyze images in Discord threads to extract usernames using Gemini API."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Ensure bot has a session for HTTP requests
        if not hasattr(self.bot, 'session'):
            import aiohttp
            self.bot.session = aiohttp.ClientSession()

    def cog_unload(self):
        pass

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_enabled(cfg: dict) -> bool:
        return cfg.get(IMAGE_ANALYSIS_ENABLED_KEY, False)

    @staticmethod
    def _get_channel_id(cfg: dict) -> Optional[int]:
        channel_id = cfg.get(IMAGE_ANALYSIS_CHANNEL_KEY)
        return int(channel_id) if channel_id else None

    @staticmethod
    def _get_gemini_api_key(cfg: dict) -> Optional[str]:
        return cfg.get(GEMINI_API_KEY_KEY)

    # ------------------------------------------------------------------
    # Gemini API integration
    # ------------------------------------------------------------------

    async def _call_gemini_api(self, image_data: bytes, api_key: str) -> Optional[str]:
        """Call Gemini API to extract usernames from image."""
        try:
            import google.generativeai as genai
            
            # Configure Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Convert image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Create prompt for username extraction
            prompt = """
            Analyze this image and extract all usernames/player names that are visible.
            
            The image shows a list of players/users organized in groups. Please extract ONLY the usernames/player names.
            
            Return the usernames as a simple comma-separated list, one username per line.
            Do not include any other text, just the usernames.
            
            Example format:
            username1
            username2
            username3
            """
            
            # Create image part
            image_part = {
                "mime_type": "image/jpeg",
                "data": image_base64
            }
            
            # Generate response
            response = model.generate_content([prompt, image_part])
            
            if response.text:
                return response.text.strip()
            else:
                _log.warning("Gemini API returned empty response")
                return None
                
        except Exception as e:
            _log.error(f"Failed to call Gemini API: {e}")
            return None

    # ------------------------------------------------------------------
    # Username extraction and processing
    # ------------------------------------------------------------------

    def _parse_usernames(self, text: str) -> List[str]:
        """Parse usernames from Gemini API response."""
        if not text:
            return []
        
        # Split by newlines and commas, clean up each username
        usernames = []
        lines = text.replace(',', '\n').split('\n')
        
        for line in lines:
            username = line.strip()
            if username and len(username) > 1:  # Filter out empty or single-character entries
                # Remove common prefixes/suffixes that might be artifacts
                username = re.sub(r'^[0-9]+\.\s*', '', username)  # Remove numbered prefixes
                username = re.sub(r'^\s*[-•*]\s*', '', username)  # Remove bullet points
                username = username.strip()
                
                if username and len(username) > 1:
                    usernames.append(username)
        
        return list(set(usernames))  # Remove duplicates

    async def _process_image(self, message: discord.Message, image_data: bytes, guild_id: int):
        """Process a single image and extract usernames."""
        cfg = storage.load_guild_config(guild_id)
        api_key = self._get_gemini_api_key(cfg)
        
        if not api_key:
            _log.warning(f"No Gemini API key configured for guild {guild_id}")
            return
        
        # Call Gemini API
        response_text = await self._call_gemini_api(image_data, api_key)
        if not response_text:
            return
        
        # Parse usernames
        usernames = self._parse_usernames(response_text)
        if not usernames:
            _log.info(f"No usernames extracted from image in message {message.id}")
            return
                
        # Send extracted usernames directly to the thread
        embed = discord.Embed(
            title="🔍 Bildanalyse abgeschlossen",
            description=f"**{len(usernames)} Benutzernamen extrahiert:**\n" + ", ".join(f"`{username}`" for username in usernames),
            color=discord.Color.green()
        )
        
        # Add timestamp
        embed.set_footer(text=f"Analysiert am {message.created_at.strftime('%d.%m.%Y um %H:%M')}")
        
        try:
            await message.reply(embed=embed)
        except discord.Forbidden:
            _log.warning(f"Cannot reply to message {message.id} in guild {guild_id}")
            # Try to send to the channel instead
            try:
                await message.channel.send(embed=embed)
            except discord.Forbidden:
                _log.error(f"Cannot send message to channel {message.channel.id} in guild {guild_id}")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Process new messages for image analysis."""
        # Skip bot messages
        if message.author.bot:
            return
        
        # Only process messages in threads
        if not isinstance(message.channel, discord.Thread):
            return
        
        # Get guild configuration
        guild = message.guild
        if not guild:
            return
        
        cfg = storage.load_guild_config(guild.id)
        if not self._is_enabled(cfg):
            return
        
        # Check if this thread belongs to the configured channel
        channel_id = self._get_channel_id(cfg)
        if not channel_id or message.channel.parent_id != channel_id:
            return
        
        # Check if message has attachments
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith('image/'):
                try:
                    # Download image
                    image_data = await attachment.read()
                    await self._process_image(message, image_data, guild.id)
                    break  # Only process first image per message
                except Exception as e:
                    _log.error(f"Failed to process image in message {message.id}: {e}")
        
        # Also check for embeds with images
        for embed in message.embeds:
            if embed.image and embed.image.url:
                try:
                    # Download image from embed
                    async with self.bot.session.get(embed.image.url) as resp:
                        if resp.status == 200:
                            image_data = await resp.read()
                            await self._process_image(message, image_data, guild.id)
                            break
                except Exception as e:
                    _log.error(f"Failed to process embed image in message {message.id}: {e}")

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @app_commands.command(name="analyze_image", description="Manuell ein Bild analysieren und Benutzernamen extrahieren.")
    @app_commands.default_permissions(manage_guild=True)
    async def analyze_image(self, interaction: discord.Interaction):
        """Manually analyze an image to extract usernames."""
        await interaction.response.defer(thinking=True)
        
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("❌ Dieser Befehl kann nur in einer Guild verwendet werden.", ephemeral=True)
            return
        
        # Check if image analysis is enabled
        cfg = storage.load_guild_config(guild.id)
        if not self._is_enabled(cfg):
            await interaction.followup.send("❌ Bildanalyse ist für diese Guild nicht aktiviert.", ephemeral=True)
            return
        
        # Check if there's a Gemini API key
        api_key = self._get_gemini_api_key(cfg)
        if not api_key:
            await interaction.followup.send("❌ Kein Gemini API-Schlüssel konfiguriert. Bitte konfiguriere ihn in der Web-UI.", ephemeral=True)
            return
        
        # Check if the command was used in a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send("❌ Dieser Befehl kann nur in Threads verwendet werden.", ephemeral=True)
            return
        
        # Look for the most recent image in the thread
        try:
            messages = [msg async for msg in interaction.channel.history(limit=20)]
            
            for message in messages:
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        try:
                            image_data = await attachment.read()
                            await self._process_image(message, image_data, guild.id)
                            await interaction.followup.send("✅ Bild erfolgreich analysiert!", ephemeral=True)
                            return
                        except Exception as e:
                            _log.error(f"Failed to process image: {e}")
                            await interaction.followup.send(f"❌ Fehler beim Analysieren des Bildes: {str(e)}", ephemeral=True)
                            return
            
            await interaction.followup.send("❌ Kein Bild in den letzten 20 Nachrichten gefunden.", ephemeral=True)
            
        except Exception as e:
            _log.error(f"Error in analyze_image command: {e}")
            await interaction.followup.send(f"❌ Fehler beim Analysieren: {str(e)}", ephemeral=True)



async def setup(bot: commands.Bot):
    await bot.add_cog(ImageAnalysis(bot)) 
