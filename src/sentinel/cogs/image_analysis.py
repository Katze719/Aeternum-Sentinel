from __future__ import annotations

import logging
import re
from typing import List, Optional, Dict
import base64
import json

import discord
from discord import app_commands
from discord.ext import commands

import sentinel.utils.storage as storage
from sentinel.integrations.google_sheets import get_async_gspread_client_manager

_log = logging.getLogger(__name__)

# Config keys
IMAGE_ANALYSIS_ENABLED_KEY = "image_analysis_enabled"
IMAGE_ANALYSIS_CHANNEL_KEY = "image_analysis_channel_id"
IMAGE_ANALYSIS_SECOND_CHANNEL_KEY = "image_analysis_second_channel_id"
GEMINI_API_KEY_KEY = "gemini_api_key"
PAYOUT_SHEET_KEY = "payout_sheet_id"
PAYOUT_WORKSHEET_KEY = "payout_worksheet_name"
PAYOUT_USER_COLUMN_KEY = "payout_user_column"
PAYOUT_EVENT_ROW_KEY = "payout_event_row"
PAYOUT_EVENT_START_COLUMN_KEY = "payout_event_start_column"
PAYOUT_LANGUAGE_KEY = "payout_language"
CONFIRMATION_ROLES_KEY = "confirmation_roles"
TEAM_STATS_SHEET_KEY = "team_stats_sheet_id"
TEAM_STATS_WORKSHEET_KEY = "team_stats_worksheet_name"

class ImageAnalysis(commands.Cog):
    """Analyze images in Discord threads to extract usernames using Gemini API."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Ensure bot has a session for HTTP requests
        if not hasattr(self.bot, 'session'):
            import aiohttp
            self.bot.session = aiohttp.ClientSession()
        
        # Store pending username edits: message_id -> {usernames: List[str], original_message_id: int}
        self._pending_edits: Dict[int, Dict] = {}

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
    def _get_second_channel_id(cfg: dict) -> Optional[int]:
        channel_id = cfg.get(IMAGE_ANALYSIS_SECOND_CHANNEL_KEY)
        return int(channel_id) if channel_id else None

    @staticmethod
    def _get_gemini_api_key(cfg: dict) -> Optional[str]:
        return cfg.get(GEMINI_API_KEY_KEY)

    @staticmethod
    def _get_payout_sheet_id(cfg: dict) -> Optional[str]:
        return cfg.get(PAYOUT_SHEET_KEY)

    @staticmethod
    def _get_payout_worksheet_name(cfg: dict) -> Optional[str]:
        return cfg.get(PAYOUT_WORKSHEET_KEY)

    @staticmethod
    def _get_payout_user_column(cfg: dict) -> Optional[str]:
        return cfg.get(PAYOUT_USER_COLUMN_KEY)

    @staticmethod
    def _get_payout_event_row(cfg: dict) -> Optional[int]:
        row = cfg.get(PAYOUT_EVENT_ROW_KEY)
        return int(row) if row else None

    @staticmethod
    def _get_payout_event_start_column(cfg: dict) -> Optional[int]:
        column = cfg.get(PAYOUT_EVENT_START_COLUMN_KEY)
        if not column:
            return None
        
        # If it's already a number, return it
        if isinstance(column, int):
            return column
        
        # If it's a string that's a number, convert it
        if isinstance(column, str) and column.isdigit():
            return int(column)
        
        # If it's a letter (A, B, C, etc.), convert to number
        if isinstance(column, str) and len(column.strip()) > 0:
            return ImageAnalysis._column_letter_to_index(column.strip()) + 1  # Convert to 1-based
        
        return None

    @staticmethod
    def _get_payout_language(cfg: dict) -> str:
        return cfg.get(PAYOUT_LANGUAGE_KEY, "de")

    @staticmethod
    def _get_confirmation_roles(cfg: dict) -> List[int]:
        """Get list of role IDs that are allowed to confirm usernames."""
        roles = cfg.get(CONFIRMATION_ROLES_KEY, [])
        if isinstance(roles, list):
            return [int(role_id) for role_id in roles if str(role_id).isdigit()]
        return []

    @staticmethod
    def _get_team_stats_sheet_id(cfg: dict) -> Optional[str]:
        return cfg.get(TEAM_STATS_SHEET_KEY)

    @staticmethod
    def _get_team_stats_worksheet_name(cfg: dict) -> Optional[str]:
        return cfg.get(TEAM_STATS_WORKSHEET_KEY)

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
            
            # Generate response using async Gemini API
            response = await model.generate_content_async([prompt, image_part])
            
            if response.text:
                return response.text.strip()
            else:
                _log.warning("Gemini API returned empty response")
                return None
                
        except Exception as e:
            _log.error(f"Failed to call Gemini API: {e}")
            return None

    async def _call_gemini_api_for_team_stats(self, image_data: bytes, api_key: str, image_type: str) -> Optional[str]:
        """Call Gemini API to extract team statistics or team composition data."""
        try:
            import google.generativeai as genai
            
            # Configure Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Convert image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            if image_type == "stats":
                prompt = """
                Analyze this image showing team statistics/leaderboard data.
                
                Extract all player statistics from the image and return them as a JSON array.
                Each player should be an object with these fields:
                - "name": the player's name/username
                - "kills": number of kills (integer)
                - "deaths": number of deaths (integer) 
                - "assists": number of assists (integer)
                - "healing": healing amount (integer, 0 if not present)
                - "damage": damage amount (integer, 0 if not present)
                
                Important: Return ONLY valid JSON, no other text or explanations.
                If you cannot extract the data, return an empty array: []
                
                Example response:
                [{"name":"Player1","kills":15,"deaths":3,"assists":8,"healing":1250000,"damage":450000},{"name":"Player2","kills":12,"deaths":5,"assists":10,"healing":980000,"damage":380000}]
                """
            else:  # team composition
                prompt = """
                Analyze this image showing team composition/group assignments.
                
                Extract all groups and their players from the image and return them as a JSON object.
                Each group should be a key in the object with an array of player names as the value.
                
                Important: Return ONLY valid JSON, no other text or explanations.
                If you cannot extract the data, return an empty object: {}
                
                Example response:
                {"Group 1":["Player1","Player2","Player3","Player4","Player5"],"Group 2":["Player6","Player7","Player8","Player9","Player10"],"Trio 1":["Player11","Player12","Player13"]}
                """
            
            # Create image part
            image_part = {
                "mime_type": "image/jpeg",
                "data": image_base64
            }
            
            # Generate response using async Gemini API
            response = await model.generate_content_async([prompt, image_part])
            
            if response.text:
                response_text = response.text.strip()
                _log.info(f"Gemini API response for {image_type}: {response_text[:200]}...")
                return response_text
            else:
                _log.warning("Gemini API returned empty response for team stats")
                return None
                
        except Exception as e:
            _log.error(f"Failed to call Gemini API for team stats: {e}")
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
        
        # Remove duplicates and sort alphabetically
        return sorted(list(set(usernames)))

    def _parse_team_stats_json(self, text: str) -> List[Dict]:
        """Parse team statistics from Gemini API JSON response."""
        if not text:
            return []
        
        # Clean up the response text
        text = text.strip()
        
        # Try to extract JSON from the response if it contains other text
        import re
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        try:
            import json
            data = json.loads(text)
            
            if isinstance(data, list):
                # Validate each item has required fields
                valid_items = []
                for item in data:
                    if isinstance(item, dict) and "name" in item:
                        # Ensure all required fields exist with defaults
                        valid_item = {
                            "name": str(item.get("name", "")),
                            "kills": int(item.get("kills", 0)),
                            "deaths": int(item.get("deaths", 0)),
                            "assists": int(item.get("assists", 0)),
                            "healing": int(item.get("healing", 0)),
                            "damage": int(item.get("damage", 0))
                        }
                        valid_items.append(valid_item)
                return valid_items
            else:
                _log.warning("Team stats response is not a list")
                return []
                
        except json.JSONDecodeError as e:
            _log.error(f"Failed to parse team stats JSON: {e}")
            _log.error(f"Raw response: {text}")
            return []
        except Exception as e:
            _log.error(f"Error parsing team stats: {e}")
            return []

    def _parse_team_composition_json(self, text: str) -> Dict[str, List[str]]:
        """Parse team composition from Gemini API JSON response."""
        if not text:
            return {}
        
        # Clean up the response text
        text = text.strip()
        
        # Try to extract JSON from the response if it contains other text
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        
        try:
            import json
            data = json.loads(text)
            
            if isinstance(data, dict):
                # Validate the structure
                valid_groups = {}
                for group_name, players in data.items():
                    if isinstance(players, list):
                        # Convert all player names to strings and filter out empty ones
                        valid_players = [str(player).strip() for player in players if str(player).strip()]
                        if valid_players:
                            valid_groups[str(group_name)] = valid_players
                return valid_groups
            else:
                _log.warning("Team composition response is not a dict")
                return {}
                
        except json.JSONDecodeError as e:
            _log.error(f"Failed to parse team composition JSON: {e}")
            _log.error(f"Raw response: {text}")
            return {}
        except Exception as e:
            _log.error(f"Error parsing team composition: {e}")
            return {}

    # ------------------------------------------------------------------
    # Google Sheets payout tracking
    # ------------------------------------------------------------------

    def _resolve_worksheet_name(self, worksheet_template: str, language: str = "de") -> str:
        """Resolve dynamic worksheet name template with placeholders."""
        import datetime
        
        now = datetime.datetime.now()
        
        # Month names in different languages
        month_names = {
            "de": {
                1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
                7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
            },
            "en": {
                1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
                7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
            },
            "fr": {
                1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
                7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
            },
            "es": {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
                7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            },
            "it": {
                1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile", 5: "Maggio", 6: "Giugno",
                7: "Luglio", 8: "Agosto", 9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
            }
        }
        
        # Default to German if language not found
        if language not in month_names:
            language = "de"
        
        # Replace placeholders
        resolved = worksheet_template
        resolved = resolved.replace("{month_name}", month_names[language][now.month])
        resolved = resolved.replace("{year}", str(now.year))
        resolved = resolved.replace("{month}", f"{now.month:02d}")
        resolved = resolved.replace("{day}", f"{now.day:02d}")
        
        return resolved

    async def _process_payout_tracking(self, usernames: List[str], thread_name: str, guild_id: int, status_callback=None) -> Dict:
        """Process payout tracking for extracted usernames."""
        cfg = storage.load_guild_config(guild_id)
        
        # Get payout configuration
        sheet_id = self._get_payout_sheet_id(cfg)
        worksheet_template = self._get_payout_worksheet_name(cfg)
        user_column = self._get_payout_user_column(cfg)
        event_row = self._get_payout_event_row(cfg)
        event_start_column = self._get_payout_event_start_column(cfg)
        payout_language = self._get_payout_language(cfg)
        
        if not all([sheet_id, worksheet_template, user_column, event_row]):
            _log.warning(f"Incomplete payout configuration for guild {guild_id}")
            return {
                "success": False,
                "message": "Payout-Konfiguration unvollständig",
                "matched_users": [],
                "unmatched_users": usernames
            }
        
        # Resolve dynamic worksheet name
        worksheet_name = self._resolve_worksheet_name(worksheet_template, payout_language)
        
        if status_callback:
            await status_callback(f"**{len(usernames)} Benutzernamen werden verarbeitet...**\n\n🔄 **Schritt 2:** Google Sheets Verbindung wird hergestellt...")
        
        try:
            # Get Google Sheets client
            mgr = get_async_gspread_client_manager()
            agc = await mgr.authorize()
            ss = await agc.open_by_key(sheet_id)
            
            # Try to get the worksheet, create it if it doesn't exist
            try:
                ws = await ss.worksheet(worksheet_name)
                _log.info(f"Using existing worksheet '{worksheet_name}' for guild {guild_id}")
                if status_callback:
                    await status_callback(f"**{len(usernames)} Benutzernamen werden verarbeitet...**\n\n🔄 **Schritt 3:** Worksheet '{worksheet_name}' wird geöffnet...")
            except Exception:
                # Worksheet doesn't exist, create it
                _log.info(f"Creating new worksheet '{worksheet_name}' for guild {guild_id}")
                if status_callback:
                    await status_callback(f"**{len(usernames)} Benutzernamen werden verarbeitet...**\n\n🔄 **Schritt 3:** Neues Worksheet '{worksheet_name}' wird erstellt...")
                ws = await ss.add_worksheet(worksheet_name, rows=1000, cols=26)
                
                # Initialize the worksheet with headers if it's new
                if event_row == 1:
                    # Create header row with event names
                    header_row = [""] * 26  # Start with empty cells
                    await ws.update([header_row], "A1:Z1")
            
            # Get all values from the sheet
            all_values = await ws.get_all_values()
            
            if status_callback:
                await status_callback(f"**{len(usernames)} Benutzernamen werden verarbeitet...**\n\n🔄 **Schritt 4:** Benutzer werden in der Payoutliste gesucht...")
            
            # Convert column letter to index (A=0, B=1, etc.)
            user_col_index = self._column_letter_to_index(user_column)
            
            # Find existing users in the payout sheet
            existing_users = []
            for row_idx, row in enumerate(all_values):
                if len(row) > user_col_index and row[user_col_index].strip():
                    existing_users.append({
                        "name": row[user_col_index].strip(),
                        "row": row_idx + 1  # 1-based row index
                    })
            
            # Match extracted usernames with existing users
            matched_users = []
            unmatched_users = []
            
            for username in usernames:
                # Try exact match first
                exact_match = next((user for user in existing_users if user["name"].lower() == username.lower()), None)
                if exact_match:
                    matched_users.append(exact_match)
                    continue
                
                # Try partial match (username contains or is contained in existing name)
                partial_match = next((user for user in existing_users 
                                    if username.lower() in user["name"].lower() 
                                    or user["name"].lower() in username.lower()), None)
                if partial_match:
                    matched_users.append(partial_match)
                    continue
                
                # No match found
                unmatched_users.append(username)
            
            if status_callback:
                await status_callback(f"**{len(usernames)} Benutzernamen werden verarbeitet...**\n\n🔄 **Schritt 5:** Event-Spalte wird vorbereitet...")
            
            # Find next empty column in event row
            event_row_idx = event_row - 1  # Convert to 0-based
            if event_row_idx >= len(all_values):
                # Extend the sheet if needed
                while len(all_values) <= event_row_idx:
                    all_values.append([""] * max(len(row) for row in all_values) if all_values else 1)
            
            event_row_data = all_values[event_row_idx]
            
            # Determine start column for searching
            start_col = 0  # Default: start from beginning
            if event_start_column is not None:
                start_col = event_start_column - 1  # Convert to 0-based
            
            # Ensure the row is long enough
            while len(event_row_data) <= start_col:
                event_row_data.append("")
            
            # First, check if an event with the same name already exists
            existing_event_col = None
            for col_idx in range(start_col, len(event_row_data)):
                if event_row_data[col_idx].strip() == thread_name:
                    existing_event_col = col_idx
                    break
            
            if existing_event_col is not None:
                # Event already exists, use existing column
                event_col_letter = self._column_index_to_letter(existing_event_col)
                _log.info(f"Event '{thread_name}' already exists in column {event_col_letter} for guild {guild_id}")
                if status_callback:
                    await status_callback(f"**{len(usernames)} Benutzernamen werden verarbeitet...**\n\n🔄 **Schritt 6:** Event '{thread_name}' bereits vorhanden in Spalte {event_col_letter}...")
            else:
                # Event doesn't exist, find next empty column and create new event
                next_empty_col = len(event_row_data)  # Default: append at end
                
                # Find the first empty cell starting from the configured start column
                for col_idx in range(start_col, len(event_row_data)):
                    if not event_row_data[col_idx].strip():
                        next_empty_col = col_idx
                        break
                
                # Create new event column
                event_col_letter = self._column_index_to_letter(next_empty_col)
                
                # Write event name (thread name) in the event row
                await ws.update_cell(event_row, next_empty_col + 1, thread_name)
                _log.info(f"Created new event '{thread_name}' in column {event_col_letter} for guild {guild_id}")
                if status_callback:
                    await status_callback(f"**{len(usernames)} Benutzernamen werden verarbeitet...**\n\n🔄 **Schritt 6:** Neues Event '{thread_name}' wird in Spalte {event_col_letter} erstellt...")
            
            # Mark participation for matched users
            # Use the correct column (either existing or new)
            target_col = existing_event_col if existing_event_col is not None else next_empty_col
            
            if status_callback:
                await status_callback(f"**{len(usernames)} Benutzernamen werden verarbeitet...**\n\n🔄 **Schritt 7:** {len(matched_users)} Benutzer werden in die Payoutliste eingetragen...")
            
            # Prepare bulk update data for matched users
            if matched_users:
                # Group users by row to create batch updates
                row_updates = {}
                for user in matched_users:
                    row = user["row"]
                    if row not in row_updates:
                        row_updates[row] = {}
                    row_updates[row][target_col] = "1"
                
                # Perform bulk updates
                for row, col_updates in row_updates.items():
                    # Create a range for this row's updates
                    min_col = min(col_updates.keys())
                    max_col = max(col_updates.keys())
                    
                    # Create row data with empty cells except for the target column
                    row_data = [""] * (max_col + 1)
                    for col, value in col_updates.items():
                        row_data[col] = value
                    
                    # Update the row
                    range_name = f"{self._column_index_to_letter(min_col)}{row}:{self._column_index_to_letter(max_col)}{row}"
                    await ws.update([row_data[min_col:max_col + 1]], range_name)
            
            # Create message with start column info if configured
            if existing_event_col is not None:
                message = f"Event '{thread_name}' bereits vorhanden in Worksheet '{worksheet_name}' Spalte {event_col_letter}"
            else:
                message = f"Event '{thread_name}' erstellt in Worksheet '{worksheet_name}' Spalte {event_col_letter}"
            
            if event_start_column is not None:
                start_col_letter = self._column_index_to_letter(event_start_column - 1)
                message += f" (ab Spalte {start_col_letter})"
            
            return {
                "success": True,
                "message": message,
                "matched_users": [user["name"] for user in matched_users],
                "unmatched_users": unmatched_users,
                "event_column": event_col_letter,
                "worksheet_name": worksheet_name
            }
            
        except Exception as e:
            _log.error(f"Failed to process payout tracking: {e}")
            return {
                "success": False,
                "message": f"Fehler bei der Payout-Verarbeitung: {str(e)}",
                "matched_users": [],
                "unmatched_users": usernames
            }

    async def _create_team_stats_table(self, team_stats: List[Dict], team_composition: Dict[str, List[str]], enemy_stats: List[Dict], guild_id: int, event_name: str, status_callback=None) -> Dict:
        """Create a structured team statistics table in Google Sheets."""
        # Ensure enemy_stats is a list
        if enemy_stats is None:
            enemy_stats = []
        
        cfg = storage.load_guild_config(guild_id)
        
        # Get team stats sheet configuration
        sheet_id = self._get_team_stats_sheet_id(cfg)
        worksheet_name = self._get_team_stats_worksheet_name(cfg)
        
        if not sheet_id or not worksheet_name:
            return {
                "success": False,
                "message": "Team Stats Sheet-Konfiguration unvollständig",
                "created_rows": 0
            }
        
        try:
            # Get Google Sheets client
            mgr = get_async_gspread_client_manager()
            agc = await mgr.authorize()
            ss = await agc.open_by_key(sheet_id)
            
            if status_callback:
                await status_callback("🔄 **Schritt 5.1:** Google Sheets Verbindung hergestellt...")
            
            # Try to get the worksheet, create it if it doesn't exist
            try:
                ws = await ss.worksheet(worksheet_name)
                _log.info(f"Using existing worksheet '{worksheet_name}' for team stats")
                if status_callback:
                    await status_callback("🔄 **Schritt 5.2:** Worksheet wird geöffnet...")
            except Exception:
                # Worksheet doesn't exist, create it
                _log.info(f"Creating new worksheet '{worksheet_name}' for team stats")
                if status_callback:
                    await status_callback("🔄 **Schritt 5.2:** Neues Worksheet wird erstellt...")
                ws = await ss.add_worksheet(worksheet_name, rows=1000, cols=50)
            
            # Start writing from row 3 (fixed structure)
            start_row = 3
            
            # Write event name in cell A1
            await ws.update_cell(1, 1, f"Event: {event_name}")
            
            if status_callback:
                await status_callback("🔄 **Schritt 5.3:** Alte Daten werden gelöscht...")
            
            # Clear existing data using bulk operations
            # Clear team stats area (rows 3-55, columns B, D, E, F, G, H)
            team_stats_clear_ranges = ["B3:B55", "D3:D55", "E3:E55", "F3:F55", "G3:G55", "H3:H55"]
            await ws.batch_clear(team_stats_clear_ranges)
            
            # Clear enemy stats area (rows 56-105, columns B, D, E, F, G, H)
            enemy_stats_clear_ranges = ["B56:B105", "D56:D105", "E56:E105", "F56:F105", "G56:G105", "H56:H105"]
            await ws.batch_clear(enemy_stats_clear_ranges)
            
            # Clear group composition area (rows 3-12, columns K, L, M, N, O, P)
            group_clear_ranges = ["K3:K12", "L3:L12", "M3:M12", "N3:N12", "O3:O12", "P3:P12"]
            await ws.batch_clear(group_clear_ranges)
            
            # Write team player statistics starting from row 3
            if status_callback:
                await status_callback("🔄 **Schritt 5.4:** Team-Statistiken werden eingetragen...")
            
            # Prepare team stats data for bulk update
            if team_stats:
                team_stats_data = []
                for i, player in enumerate(team_stats):
                    row = start_row + i
                    # Create row data: [Name, "", Kills, Deaths, Assists, Healing, Damage]
                    row_data = [
                        player.get("name", ""),  # B column
                        "",  # C column (empty)
                        player.get("kills", 0),  # D column
                        player.get("deaths", 0),  # E column
                        player.get("assists", 0),  # F column
                        player.get("healing", 0),  # G column
                        player.get("damage", 0)   # H column
                    ]
                    team_stats_data.append(row_data)
                
                # Bulk update team stats
                team_stats_range = f"B{start_row}:H{start_row + len(team_stats) - 1}"
                await ws.update(team_stats_data, team_stats_range)
            
            # Write enemy player statistics starting from row 56
            if status_callback:
                await status_callback("🔄 **Schritt 5.5:** Gegner-Statistiken werden eingetragen...")
            
            # Prepare enemy stats data for bulk update
            if enemy_stats:
                enemy_stats_data = []
                enemy_start_row = 56
                for i, player in enumerate(enemy_stats):
                    row = enemy_start_row + i
                    # Create row data: [Name, "", Kills, Deaths, Assists, Healing, Damage]
                    row_data = [
                        player.get("name", ""),  # B column
                        "",  # C column (empty)
                        player.get("kills", 0),  # D column
                        player.get("deaths", 0),  # E column
                        player.get("assists", 0),  # F column
                        player.get("healing", 0),  # G column
                        player.get("damage", 0)   # H column
                    ]
                    enemy_stats_data.append(row_data)
                
                # Bulk update enemy stats
                enemy_stats_range = f"B{enemy_start_row}:H{enemy_start_row + len(enemy_stats) - 1}"
                await ws.update(enemy_stats_data, enemy_stats_range)
            
            # Write group composition starting from row 3
            if status_callback:
                await status_callback("🔄 **Schritt 5.6:** Gruppen-Zusammensetzung wird eingetragen...")
            
            # Prepare group composition data for bulk update
            if team_composition:
                group_data = []
                for i, (group_name, players) in enumerate(team_composition.items()):
                    row = start_row + i
                    # Create row data for columns K-P: [Group Name, Player1, Player2, Player3, Player4, Player5]
                    row_data = [""] * 6  # Initialize with empty strings for K-P columns
                    row_data[0] = group_name  # K column (index 0 in our 6-column array)
                    
                    # Add players to columns L, M, N, O, P (indices 1-5 in our 6-column array)
                    for j, player in enumerate(players[:5]):  # Max 5 players per group
                        row_data[1 + j] = player
                    
                    group_data.append(row_data)
                
                # Bulk update group composition
                group_range = f"K{start_row}:P{start_row + len(team_composition) - 1}"
                await ws.update(group_data, group_range)
                
                return {
                    "success": True,
                    "message": f"Team Statistics Tabelle erstellt in '{worksheet_name}' ab Zeile 3",
                    "created_rows": len(team_stats) + len(team_composition),
                    "worksheet_name": worksheet_name
                }
            
        except Exception as e:
            _log.error(f"Failed to create team stats table: {e}")
            _log.exception("Full traceback for team stats table creation error:")
            return {
                "success": False,
                "message": f"Fehler beim Erstellen der Team Statistics Tabelle: {str(e)}",
                "created_rows": 0
            }

    @staticmethod
    def _column_letter_to_index(column: str) -> int:
        """Convert column letter to 0-based index (A=0, B=1, etc.)."""
        result = 0
        for char in column.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1

    @staticmethod
    def _column_index_to_letter(index: int) -> str:
        """Convert 0-based index to column letter (0=A, 1=B, etc.)."""
        result = ""
        while index >= 0:
            result = chr(index % 26 + 65) + result
            index = index // 26 - 1
        return result

    async def _process_image(self, message: discord.Message, image_data: bytes, guild_id: int):
        """Process a single image and extract usernames."""
        # Get the original image URL from the message
        image_url = None
        if message.attachments:
            # Use the first image attachment
            image_url = message.attachments[0].url
        elif message.embeds:
            # Check embeds for images
            for embed in message.embeds:
                if embed.image and embed.image.url:
                    image_url = embed.image.url
                    break
        
        # Create confirmation embed
        embed = discord.Embed(
            title="🖼️ Bild zur Analyse gefunden",
            description="Ein Bild wurde in diesem Thread hochgeladen. Soll eine Text-Extraktion durchgeführt werden?",
            color=discord.Color.blue()
        )
        
        # Add the original image to the embed if available
        if image_url:
            embed.set_image(url=image_url)
        
        embed.add_field(
            name="ℹ️ Was passiert?",
            value=f"• Ein event mit dem Namen **{message.channel.name}** wird erstellt oder verwendet\n• Benutzernamen werden automatisch extrahiert\n• Du kannst die Liste bearbeiten und bestätigen\n• Die Nutzer werden in die Payoutliste eingetragen",
            inline=False
        )
        embed.set_footer(text=f"Hochgeladen am {message.created_at.strftime('%d.%m.%Y um %H:%M')}")
        
        # Create confirmation buttons
        view = ImageAnalysisConfirmationView(self, message, image_data, guild_id)
        
        try:
            # Send confirmation message
            confirmation_msg = await message.reply(embed=embed, view=view)
            
        except discord.Forbidden:
            _log.warning(f"Cannot reply to message {message.id} in guild {guild_id}")
            # Try to send to the channel instead
            try:
                confirmation_msg = await message.channel.send(embed=embed, view=view)
            except discord.Forbidden:
                _log.error(f"Cannot send message to channel {message.channel.id} in guild {guild_id}")

    async def _analyze_image_and_extract_usernames(self, message: discord.Message, image_data: bytes, guild_id: int):
        """Actually perform the image analysis and extract usernames."""
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
        
        # Get the original image URL from the message
        image_url = None
        if message.attachments:
            # Use the first image attachment
            image_url = message.attachments[0].url
        elif message.embeds:
            # Check embeds for images
            for embed in message.embeds:
                if embed.image and embed.image.url:
                    image_url = embed.image.url
                    break
                
        # Create interactive embed with buttons
        embed = discord.Embed(
            title="🔍 Bildanalyse abgeschlossen",
            description=f"**{len(usernames)} Benutzernamen extrahiert:**\n" + ", ".join(f"`{username}`" for username in usernames),
            color=discord.Color.blue()
        )
        
        # Add the original image to the embed if available
        if image_url:
            embed.set_image(url=image_url)
        
        embed.add_field(
            name="📝 Bearbeitung",
            value="Verwende die Buttons unten, um Benutzernamen hinzuzufügen oder zu entfernen, bevor du sie bestätigst.",
            inline=False
        )
        embed.set_footer(text=f"Analysiert am {message.created_at.strftime('%d.%m.%Y um %H:%M')}")
        
        # Create buttons
        view = UsernameEditView(self, usernames, message.id, message.channel.name, guild_id)
        
        # Configure buttons based on permissions
        await view._configure_buttons_for_user(message.guild)
        
        try:
            # Send interactive message
            interactive_msg = await message.reply(embed=embed, view=view)
            
            # Store pending edit data
            self._pending_edits[interactive_msg.id] = {
                "usernames": usernames.copy(),
                "original_message_id": message.id
            }
            
        except discord.Forbidden:
            _log.warning(f"Cannot reply to message {message.id} in guild {guild_id}")
            # Try to send to the channel instead
            try:
                interactive_msg = await message.channel.send(embed=embed, view=view)
                self._pending_edits[interactive_msg.id] = {
                    "usernames": usernames.copy(),
                    "original_message_id": message.id
                }
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
        
        # Check if this thread belongs to one of the configured channels
        channel_id = self._get_channel_id(cfg)
        second_channel_id = self._get_second_channel_id(cfg)
        
        # Check if thread belongs to either configured channel
        if not channel_id and not second_channel_id:
            return
        
        if channel_id and message.channel.parent_id == channel_id:
            pass  # First channel matches
        elif second_channel_id and message.channel.parent_id == second_channel_id:
            pass  # Second channel matches
        else:
            return  # Thread doesn't belong to any configured channel
        
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
                            await interaction.followup.send("✅ Bestätigungsnachricht für Bildanalyse gesendet!", ephemeral=True)
                            return
                        except Exception as e:
                            _log.error(f"Failed to process image: {e}")
                            await interaction.followup.send(f"❌ Fehler beim Analysieren des Bildes: {str(e)}", ephemeral=True)
                            return
            
            await interaction.followup.send("❌ Kein Bild in den letzten 20 Nachrichten gefunden.", ephemeral=True)
            
        except Exception as e:
            _log.error(f"Error in analyze_image command: {e}")
            await interaction.followup.send(f"❌ Fehler beim Analysieren: {str(e)}", ephemeral=True)

    @app_commands.command(name="create_team_stats", description="Team-Statistiken, Team-Zusammensetzung und Gegner-Statistiken verarbeiten und Tabelle erstellen.")
    @app_commands.describe(
        stats_image_url="URL zum Bild mit Team-Statistiken (Leaderboard)",
        composition_image_url="URL zum Bild mit Team-Zusammensetzung (Gruppen)",
        enemy_stats_image_url="URL zum Bild mit Gegner-Statistiken"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def create_team_stats(self, interaction: discord.Interaction, stats_image_url: str, composition_image_url: str, enemy_stats_image_url: str):
        """Process team statistics and team composition images to create a structured table."""
        await interaction.response.defer(thinking=True)
        
        guild = interaction.guild
        if guild is None:
            embed = discord.Embed(
                title="❌ Fehler",
                description="Dieser Befehl kann nur in einer Guild verwendet werden.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed)
            return
        
        # Check if image analysis is enabled
        cfg = storage.load_guild_config(guild.id)
        if not self._is_enabled(cfg):
            embed = discord.Embed(
                title="❌ Bildanalyse nicht aktiviert",
                description="Bildanalyse ist für diese Guild nicht aktiviert.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed)
            return
        
        # Check if there's a Gemini API key
        api_key = self._get_gemini_api_key(cfg)
        if not api_key:
            embed = discord.Embed(
                title="❌ Kein Gemini API-Schlüssel",
                description="Kein Gemini API-Schlüssel konfiguriert. Bitte konfiguriere ihn in der Web-UI.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed)
            return
        
        # Check if team stats sheet is configured
        sheet_id = self._get_team_stats_sheet_id(cfg)
        worksheet_name = self._get_team_stats_worksheet_name(cfg)
        if not sheet_id or not worksheet_name:
            embed = discord.Embed(
                title="❌ Team Stats Sheet nicht konfiguriert",
                description="Team Stats Sheet-Konfiguration unvollständig. Bitte konfiguriere sie in der Web-UI.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed)
            return
        
        try:
            # Create status update function that edits the original message
            async def update_status(message):
                embed = discord.Embed(
                    title="⏳ Team Statistics werden verarbeitet...",
                    description=message,
                    color=discord.Color.yellow()
                )
                await interaction.edit_original_response(embed=embed)
            
            # Download images from URLs
            stats_image_data = None
            composition_image_data = None
            enemy_stats_image_data = None
            
            await update_status("🔄 **Schritt 1:** Bilder werden heruntergeladen...")
            
            try:
                # Download stats image
                async with self.bot.session.get(stats_image_url) as resp:
                    if resp.status != 200:
                        embed = discord.Embed(
                            title="❌ Fehler beim Herunterladen des Stats-Bildes",
                            description=f"HTTP Status: {resp.status}",
                            color=discord.Color.red()
                        )
                        await interaction.edit_original_response(embed=embed)
                        return
                    stats_image_data = await resp.read()
                
                # Download composition image
                async with self.bot.session.get(composition_image_url) as resp:
                    if resp.status != 200:
                        embed = discord.Embed(
                            title="❌ Fehler beim Herunterladen des Composition-Bildes",
                            description=f"HTTP Status: {resp.status}",
                            color=discord.Color.red()
                        )
                        await interaction.edit_original_response(embed=embed)
                        return
                    composition_image_data = await resp.read()
                
                # Download enemy stats image
                async with self.bot.session.get(enemy_stats_image_url) as resp:
                    if resp.status != 200:
                        embed = discord.Embed(
                            title="❌ Fehler beim Herunterladen des Gegner-Stats-Bildes",
                            description=f"HTTP Status: {resp.status}",
                            color=discord.Color.red()
                        )
                        await interaction.edit_original_response(embed=embed)
                        return
                    enemy_stats_image_data = await resp.read()
                    
            except Exception as e:
                _log.error(f"Failed to download images: {e}")
                embed = discord.Embed(
                    title="❌ Fehler beim Herunterladen der Bilder",
                    description=str(e),
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed)
                return
            
            # Process team statistics image
            await update_status("🔄 **Schritt 2:** Team-Statistiken werden analysiert...")
            stats_response = await self._call_gemini_api_for_team_stats(stats_image_data, api_key, "stats")
            if not stats_response:
                embed = discord.Embed(
                    title="❌ Konnte keine Team-Statistiken extrahieren",
                    description="Das Stats-Bild konnte nicht verarbeitet werden.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed)
                return
            
            team_stats = self._parse_team_stats_json(stats_response)
            if not team_stats:
                embed = discord.Embed(
                    title="❌ Konnte keine gültigen Team-Statistiken extrahieren",
                    description="Das Stats-Bild enthielt keine verwertbaren Daten.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed)
                return
            
            # Process team composition image
            await update_status("🔄 **Schritt 3:** Team-Zusammensetzung wird analysiert...")
            composition_response = await self._call_gemini_api_for_team_stats(composition_image_data, api_key, "composition")
            if not composition_response:
                embed = discord.Embed(
                    title="❌ Konnte keine Team-Zusammensetzung extrahieren",
                    description="Das Composition-Bild konnte nicht verarbeitet werden.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed)
                return
            
            team_composition = self._parse_team_composition_json(composition_response)
            if not team_composition:
                embed = discord.Embed(
                    title="❌ Konnte keine gültige Team-Zusammensetzung extrahieren",
                    description="Das Composition-Bild enthielt keine verwertbaren Daten.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed)
                return
            
            # Process enemy statistics image
            await update_status("🔄 **Schritt 4:** Gegner-Statistiken werden analysiert...")
            enemy_response = await self._call_gemini_api_for_team_stats(enemy_stats_image_data, api_key, "stats")
            if not enemy_response:
                embed = discord.Embed(
                    title="❌ Konnte keine Gegner-Statistiken extrahieren",
                    description="Das Gegner-Stats-Bild konnte nicht verarbeitet werden.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed)
                return
            
            enemy_stats = self._parse_team_stats_json(enemy_response)
            if not enemy_stats:
                embed = discord.Embed(
                    title="❌ Konnte keine gültigen Gegner-Statistiken extrahieren",
                    description="Das Gegner-Stats-Bild enthielt keine verwertbaren Daten.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed)
                return
            
            # Create the table in Google Sheets
            await update_status("🔄 **Schritt 5:** Google Sheets Tabelle wird erstellt...")
            event_name = interaction.channel.name if isinstance(interaction.channel, discord.Thread) else "Team Statistics"
            result = await self._create_team_stats_table(team_stats, team_composition, enemy_stats, guild.id, event_name, update_status)
            
            if result["success"]:
                embed = discord.Embed(
                    title="✅ Team Statistics Tabelle erstellt",
                    description=result["message"],
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📊 Verarbeitete Daten",
                    value=f"• **{len(team_stats)}** Team-Spieler-Statistiken\n• **{len(enemy_stats)}** Gegner-Spieler-Statistiken\n• **{len(team_composition)}** Gruppen\n• **{result['created_rows']}** Zeilen erstellt",
                    inline=False
                )
                embed.add_field(
                    name="📋 Gefundene Gruppen",
                    value="\n".join([f"• {group}" for group in team_composition.keys()]),
                    inline=False
                )
                embed.set_footer(text=f"Erstellt von {interaction.user.display_name}")
                
                await interaction.edit_original_response(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Fehler beim Erstellen der Tabelle",
                    description=result['message'],
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed)
            
        except Exception as e:
            _log.error(f"Error in create_team_stats command: {e}")
            embed = discord.Embed(
                title="❌ Fehler beim Verarbeiten der Team-Statistiken",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed)


class ImageAnalysisConfirmationView(discord.ui.View):
    """Confirmation view for image analysis."""
    
    def __init__(self, cog: ImageAnalysis, message: discord.Message, image_data: bytes, guild_id: int):
        super().__init__(timeout=259200) 
        self.cog = cog
        self.message = message
        self.image_data = image_data
        self.guild_id = guild_id

    @discord.ui.button(label="Ja, analysieren", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_analysis(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm image analysis."""
        # Disable all buttons immediately
        for child in self.children:
            child.disabled = True
        
        # Update the message to show processing
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.yellow()
        embed.title = "⏳ Analyse läuft..."
        embed.description = "Nutzer werden extrahiert..."
        embed.remove_field(0)  # Remove the info field
        embed.set_footer(text=f"Hochgeladen am {self.message.created_at.strftime('%d.%m.%Y um %H:%M')} • Wird analysiert...")
        
        await interaction.message.edit(embed=embed, view=self)
        
        # Acknowledge the interaction immediately
        await interaction.response.defer(thinking=False)
        
        # Perform the actual analysis
        await self.cog._analyze_image_and_extract_usernames(self.message, self.image_data, self.guild_id)
        
        # Delete the confirmation message after analysis
        try:
            await interaction.message.delete()
        except discord.Forbidden:
            _log.warning(f"Cannot delete confirmation message {interaction.message.id}")

    @discord.ui.button(label="Nein, abbrechen", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel_analysis(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel image analysis."""
        await interaction.response.send_message("❌ Bildanalyse abgebrochen.", ephemeral=True)
        await interaction.message.delete()


class UsernameEditView(discord.ui.View):
    """Interactive view for editing extracted usernames."""
    
    def __init__(self, cog: ImageAnalysis, usernames: List[str], original_message_id: int, thread_name: str, guild_id: int):
        super().__init__(timeout=259200) 
        self.cog = cog
        self.usernames = usernames.copy()
        self.original_message_id = original_message_id
        self.thread_name = thread_name
        self.guild_id = guild_id

    @discord.ui.button(label="Bearbeiten", style=discord.ButtonStyle.blurple, emoji="✏️")
    async def edit_usernames(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit usernames via modal."""
        await interaction.response.send_modal(EditUsernamesModal(self))

    @discord.ui.button(label="Bestätigen", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_usernames(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm and send the final list of usernames."""
        # Check if user has permission to confirm
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ Dieser Befehl kann nur in einer Guild verwendet werden.", ephemeral=True)
            return
        
        # Load guild configuration
        cfg = storage.load_guild_config(guild.id)
        confirmation_roles = self.cog._get_confirmation_roles(cfg)
        
        # Check if user has required roles
        user_roles = [role.id for role in interaction.user.roles]
        
        has_permission = False
        
        # Check specific roles - user needs at least ONE of the configured roles
        if confirmation_roles:
            # Convert confirmation_roles to integers for comparison
            confirmation_role_ids = [int(role_id) for role_id in confirmation_roles if str(role_id).isdigit()]
            has_permission = any(role_id in user_roles for role_id in confirmation_role_ids)
        else:
            # If no roles configured, allow everyone (default behavior)
            has_permission = True
        
        if not has_permission:
            role_names = []
            for role_id in confirmation_roles:
                role = guild.get_role(role_id)
                if role:
                    role_names.append(role.name)
            
            if role_names:
                await interaction.response.send_message(
                    f"❌ Du hast keine Berechtigung, Benutzernamen zu bestätigen. "
                    f"Benötigte Rollen: {', '.join(role_names)}", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Du hast keine Berechtigung, Benutzernamen zu bestätigen.", 
                    ephemeral=True
                )
            return
        
        # Immediately disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Update the message immediately to show buttons are disabled
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.yellow()
        embed.title = "⏳ Verarbeitung läuft..."
        embed.description = f"**{len(self.usernames)} Benutzernamen werden verarbeitet...**"
        embed.remove_field(0)  # Remove the instruction field
        embed.set_footer(text=f"Analysiert am {interaction.message.created_at.strftime('%d.%m.%Y um %H:%M')} • Wird verarbeitet...")
        
        await interaction.message.edit(embed=embed, view=self)
        
        # Acknowledge the interaction immediately to avoid timeout
        await interaction.response.defer(thinking=False)
        
        # Update status: Starting payout tracking
        embed.description = f"**{len(self.usernames)} Benutzernamen werden verarbeitet...**\n\n🔄 **Schritt 1:** Payout-Tracking wird vorbereitet..."
        await interaction.message.edit(embed=embed, view=self)
        
        # Create status callback function
        async def update_status(description):
            embed.description = description
            await interaction.message.edit(embed=embed, view=self)
        
        # Process payout tracking in background with status updates
        payout_result = await self.cog._process_payout_tracking(self.usernames, self.thread_name, interaction.guild.id, update_status)
        
        # Update the original embed with final results
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ Benutzernamen bestätigt"
        embed.description = f"Die Benutzernamen ({len(self.usernames)}) wurden erfolgreich bestätigt und in die Payout-Tabelle eingetragen."
        
        # Preserve the original image if it exists
        original_image = interaction.message.embeds[0].image
        if original_image and original_image.url:
            embed.set_image(url=original_image.url)
        
        # Add payout tracking results as fields
        if payout_result["success"]:
            embed.add_field(
                name="📊 Payout-Tracking",
                value=payout_result['message'],
                inline=False
            )
            
            if payout_result["matched_users"]:
                embed.add_field(
                    name=f"✅ Gefundene / Eingetragene Benutzer ({len(payout_result['matched_users'])})",
                    value=", ".join(f"`{user}`" for user in payout_result["matched_users"]),
                    inline=False
                )
            
            if payout_result["unmatched_users"]:
                embed.add_field(
                    name=f"⚠️ Nicht Gefunden / Eingetragene Benutzer ({len(payout_result['unmatched_users'])})",
                    value=", ".join(f"`{user}`" for user in payout_result["unmatched_users"]),
                    inline=False
                )
        else:
            embed.add_field(
                name="❌ Payout-Tracking fehlgeschlagen",
                value=payout_result['message'],
                inline=False
            )
            embed.color = discord.Color.red()
        
        # Update footer to include who confirmed it
        embed.set_footer(text=f"Analysiert am {interaction.message.created_at.strftime('%d.%m.%Y um %H:%M')} • Bestätigt von {interaction.user.display_name}")
        
        # Update the message with final results
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Abbrechen", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel_analysis(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the analysis and delete the message."""
        await interaction.response.send_message("❌ Bildanalyse abgebrochen.", ephemeral=True)
        await interaction.message.delete()

    async def _configure_buttons_for_user(self, guild: discord.Guild):
        """Configure buttons based on user permissions."""
        # This method is kept for future use if needed
        # For now, we'll handle permissions at button click time
        pass

    async def _update_message(self, interaction: discord.Interaction):
        """Update the message with current usernames."""
        embed = interaction.message.embeds[0]
        embed.description = f"**{len(self.usernames)} Benutzernamen:**\n" + ", ".join(f"`{username}`" for username in self.usernames)
        
        # Preserve the image if it exists
        if not embed.image and interaction.message.embeds[0].image:
            embed.set_image(url=interaction.message.embeds[0].image.url)
        
        await interaction.message.edit(embed=embed)


class EditUsernamesModal(discord.ui.Modal, title="Benutzernamen bearbeiten"):
    """Modal for editing all usernames at once."""
    
    def __init__(self, view: UsernameEditView):
        super().__init__()
        self.view = view
        # Set the default value for the text input
        self.usernames_text.default = "\n".join(view.usernames)

    usernames_text = discord.ui.TextInput(
        label="Benutzernamen (ein Name pro Zeile)",
        placeholder="username1\nusername2\nusername3",
        required=True,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Parse usernames from text
        lines = self.usernames_text.value.strip().split('\n')
        new_usernames = []
        
        for line in lines:
            username = line.strip()
            if username and len(username) > 1:
                new_usernames.append(username)
        
        if new_usernames:
            self.view.usernames = sorted(list(new_usernames))  # Remove duplicates and sort alphabetically
            await self.view._update_message(interaction)
            await interaction.response.send_message(f"✅ {len(self.view.usernames)} Benutzernamen aktualisiert.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Keine gültigen Benutzernamen gefunden.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ImageAnalysis(bot)) 
 