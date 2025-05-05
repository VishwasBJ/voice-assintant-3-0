import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox, simpledialog
import customtkinter as ctk
import speech_recognition as sr
import pyttsx3
import threading
import json
import os
import datetime
import webbrowser
import random
import subprocess
import platform
import logging
import pickle
import requests
import re
import base64
import hashlib
import time
import unittest
import wave
import pyaudio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageEnhance
from telethon import TelegramClient, events, sync
from telethon.tl.types import InputPeerUser
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='jarvis.log'
)
logger = logging.getLogger('JarvisAssistant')

class Contact:
    def __init__(self, name, telegram_username=None, phone=None, email=None):
        self.name = name
        self.telegram_username = telegram_username
        self.phone = phone
        self.email = email
        self.last_contacted = None
        self.contact_frequency = 0  # Number of times contacted
    
    def update_contact_time(self):
        self.last_contacted = datetime.datetime.now()
        self.contact_frequency += 1

class UserProfile:
    def __init__(self, name="", location=""):
        self.name = name
        self.location = location
        self.preferences = {
            "voice_speed": 180,
            "voice_gender": "Male",  # Default to male for Jarvis
            "theme": "dark",  # Default to dark theme for Jarvis
            "favorite_apps": [],
            "frequent_commands": {},
            "feedback_ratings": []
        }
        self.command_history = []
        self.learning_data = {}
        self.contacts = {}  # Dictionary of Contact objects
        self.telegram_session = None
        self.authenticated = False
        self.auth_token = None
        self.auth_expiry = None
    
    def add_command_to_history(self, command):
        self.command_history.append({
            "command": command,
            "timestamp": datetime.datetime.now().isoformat()
        })
        # Keep only the last 100 commands
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]
    
    def update_frequent_commands(self, command_type):
        if command_type in self.preferences["frequent_commands"]:
            self.preferences["frequent_commands"][command_type] += 1
        else:
            self.preferences["frequent_commands"][command_type] = 1
    
    def add_feedback(self, rating, comment=""):
        self.preferences["feedback_ratings"].append({
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.datetime.now().isoformat()
        })
    
    def get_favorite_apps(self):
        return self.preferences.get("favorite_apps", [])
    
    def add_favorite_app(self, app_name):
        if app_name not in self.preferences["favorite_apps"]:
            self.preferences["favorite_apps"].append(app_name)
    
    def remove_favorite_app(self, app_name):
        if app_name in self.preferences["favorite_apps"]:
            self.preferences["favorite_apps"].remove(app_name)
    
    def get_most_frequent_commands(self, limit=5):
        sorted_commands = sorted(
            self.preferences["frequent_commands"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_commands[:limit]
    
    def update_learning_data(self, command, response, success):
        if command not in self.learning_data:
            self.learning_data[command] = {
                "responses": {},
                "total_uses": 0,
                "successful_uses": 0
            }
        
        self.learning_data[command]["total_uses"] += 1
        if success:
            self.learning_data[command]["successful_uses"] += 1
        
        if response in self.learning_data[command]["responses"]:
            self.learning_data[command]["responses"][response] += 1
        else:
            self.learning_data[command]["responses"][response] = 1
    
    def add_contact(self, contact):
        self.contacts[contact.name.lower()] = contact
    
    def get_contact(self, name):
        return self.contacts.get(name.lower())
    
    def remove_contact(self, name):
        if name.lower() in self.contacts:
            del self.contacts[name.lower()]
            return True
        return False
    
    def get_all_contacts(self):
        return list(self.contacts.values())
    
    def set_telegram_session(self, session_name):
        self.telegram_session = session_name
    
    def authenticate(self, password):
        # Simple authentication mechanism
        # In a real application, use a more secure method
        salt = b'jarvis_salt'  # Should be stored securely
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        
        # Generate a token that expires in 24 hours
        self.auth_token = hashlib.sha256(os.urandom(32)).hexdigest()
        self.auth_expiry = datetime.datetime.now() + datetime.timedelta(hours=24)
        self.authenticated = True
        
        return self.auth_token
    
    def is_authenticated(self, token=None):
        if not self.authenticated or not self.auth_expiry:
            return False
        
        if datetime.datetime.now() > self.auth_expiry:
            self.authenticated = False
            return False
        
        if token and token != self.auth_token:
            return False
        
        return True
    
    def logout(self):
        self.authenticated = False
        self.auth_token = None
        self.auth_expiry = None

class ProfileManager:
    def __init__(self, profiles_dir="profiles", encryption_key=None):
        self.profiles_dir = profiles_dir
        self.current_profile = None
        self.profiles = {}
        self.encryption_key = encryption_key or Fernet.generate_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Create profiles directory if it doesn't exist
        if not os.path.exists(profiles_dir):
            os.makedirs(profiles_dir)
        
        self.load_profiles()
    
    def load_profiles(self):
        try:
            profile_files = [f for f in os.listdir(self.profiles_dir) if f.endswith('.profile')]
            for profile_file in profile_files:
                profile_path = os.path.join(self.profiles_dir, profile_file)
                try:
                    with open(profile_path, 'rb') as f:
                        encrypted_data = f.read()
                        decrypted_data = self.cipher_suite.decrypt(encrypted_data)
                        profile = pickle.loads(decrypted_data)
                        self.profiles[profile.name] = profile
                except Exception as e:
                    # If decryption fails, try loading without decryption (for backward compatibility)
                    try:
                        with open(profile_path, 'rb') as f:
                            profile = pickle.load(f)
                            self.profiles[profile.name] = profile
                    except:
                        logger.error(f"Error loading profile {profile_file}: {e}")
            
            logger.info(f"Loaded {len(self.profiles)} profiles")
        except Exception as e:
            logger.error(f"Error loading profiles: {e}")
    
    def save_profile(self, profile):
        try:
            profile_path = os.path.join(self.profiles_dir, f"{profile.name}.profile")
            
            # Encrypt the profile data
            profile_data = pickle.dumps(profile)
            encrypted_data = self.cipher_suite.encrypt(profile_data)
            
            with open(profile_path, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info(f"Saved profile: {profile.name}")
            return True
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            return False
    
    def create_profile(self, name, location=""):
        if name in self.profiles:
            return False
        
        profile = UserProfile(name, location)
        self.profiles[name] = profile
        self.save_profile(profile)
        return True
    
    def delete_profile(self, name):
        if name not in self.profiles:
            return False
        
        try:
            profile_path = os.path.join(self.profiles_dir, f"{name}.profile")
            if os.path.exists(profile_path):
                os.remove(profile_path)
            
            del self.profiles[name]
            logger.info(f"Deleted profile: {name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting profile: {e}")
            return False
    
    def set_current_profile(self, name):
        if name in self.profiles:
            self.current_profile = self.profiles[name]
            return True
        return False
    
    def get_profile_names(self):
        return list(self.profiles.keys())
    
    def get_current_profile(self):
        return self.current_profile
    
    def export_encryption_key(self, path):
        try:
            with open(path, 'wb') as f:
                f.write(self.encryption_key)
            return True
        except Exception as e:
            logger.error(f"Error exporting encryption key: {e}")
            return False
    
    def import_encryption_key(self, path):
        try:
            with open(path, 'rb') as f:
                self.encryption_key = f.read()
                self.cipher_suite = Fernet(self.encryption_key)
            return True
        except Exception as e:
            logger.error(f"Error importing encryption key: {e}")
            return False

class TelegramIntegration:
    def __init__(self, api_id=None, api_hash=None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.client = None
        self.connected = False
        self.error_message = ""
    
    def initialize(self, session_name="jarvis_telegram"):
        if not self.api_id or not self.api_hash:
            self.error_message = "API ID and API Hash are required"
            return False
        
        try:
            # Create the client and connect
            self.client = TelegramClient(session_name, self.api_id, self.api_hash)
            self.client.start()
            self.connected = True
            logger.info("Telegram client initialized successfully")
            return True
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"Error initializing Telegram client: {e}")
            return False
    
    def get_contacts(self):
        if not self.connected or not self.client:
            return []
        
        try:
            contacts = []
            for dialog in self.client.iter_dialogs():
                if dialog.is_user:
                    contacts.append({
                        "name": dialog.name,
                        "username": dialog.entity.username if hasattr(dialog.entity, 'username') else None,
                        "id": dialog.id
                    })
            return contacts
        except Exception as e:
            logger.error(f"Error getting Telegram contacts: {e}")
            return []
    
    def send_message(self, recipient, message):
        if not self.connected or not self.client:
            return False, "Not connected to Telegram"
        
        try:
            # Try to find the recipient by username or name
            entity = None
            
            # If recipient is a username (starts with @)
            if recipient.startswith('@'):
                username = recipient[1:]  # Remove the @ symbol
                entity = self.client.get_entity(username)
            else:
                # Search for the recipient in dialogs
                for dialog in self.client.iter_dialogs():
                    if dialog.name.lower() == recipient.lower():
                        entity = dialog.entity
                        break
            
            if not entity:
                return False, f"Could not find recipient: {recipient}"
            
            # Send the message
            self.client.send_message(entity, message)
            logger.info(f"Message sent to {recipient}")
            return True, f"Message sent to {recipient}"
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error sending Telegram message: {error_msg}")
            return False, f"Error sending message: {error_msg}"
    
    def disconnect(self):
        if self.client:
            try:
                self.client.disconnect()
                self.connected = False
                logger.info("Telegram client disconnected")
                return True
            except Exception as e:
                logger.error(f"Error disconnecting Telegram client: {e}")
                return False
        return True

class AppLauncher:
    def __init__(self):
        self.os_name = platform.system()
        self.app_paths = self._get_default_app_paths()
        self.launch_history = []
    
    def _get_default_app_paths(self):
        paths = {
            "spotify": {
                "Windows": r"C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe",
                "Darwin": "/Applications/Spotify.app",  # macOS
                "Linux": "spotify"
            },
            "chrome": {
                "Windows": r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                "Darwin": "/Applications/Google Chrome.app",  # macOS
                "Linux": "google-chrome"
            },
            "firefox": {
                "Windows": r"C:\Program Files\Mozilla Firefox\firefox.exe",
                "Darwin": "/Applications/Firefox.app",  # macOS
                "Linux": "firefox"
            },
            "telegram": {
                "Windows": r"E:\Telegram Desktop\Telegram.exe",
                "Darwin": "/Applications/Telegram.app",  # macOS
                "Linux": "telegram-desktop"
            },
            "notepad": {
                "Windows": "notepad.exe",
                "Darwin": "/Applications/TextEdit.app",  # macOS
                "Linux": "gedit"
            },
            "calculator": {
                "Windows": "calc.exe",
                "Darwin": "/Applications/Calculator.app",  # macOS
                "Linux": "gnome-calculator"
            }
        }
        return paths
    
    def launch_app(self, app_name):
        app_name = app_name.lower()
        
        try:
            if app_name in self.app_paths:
                app_path = self.app_paths[app_name].get(self.os_name)
                
                if not app_path:
                    return False, f"Application {app_name} is not supported on {self.os_name}"
                
                if self.os_name == "Windows":
                    # Handle environment variables in Windows paths
                    if "%USERNAME%" in app_path:
                        username = os.environ.get("USERNAME", "")
                        app_path = app_path.replace("%USERNAME%", username)
                    
                    subprocess.Popen([app_path])
                
                elif self.os_name == "Darwin":  # macOS
                    subprocess.Popen(["open", app_path])
                
                elif self.os_name == "Linux":
                    subprocess.Popen([app_path])
                
                # Record the launch in history
                self.launch_history.append({
                    "app": app_name,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "success": True
                })
                
                logger.info(f"Launched application: {app_name}")
                return True, f"Launched {app_name} successfully"
            
            else:
                # Try to launch by name if it's not in our predefined list
                if self.os_name == "Windows":
                    subprocess.Popen([app_name])
                elif self.os_name == "Darwin":  # macOS
                    subprocess.Popen(["open", "-a", app_name])
                elif self.os_name == "Linux":
                    subprocess.Popen([app_name])
                
                # Record the launch in history
                self.launch_history.append({
                    "app": app_name,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "success": True
                })
                
                logger.info(f"Attempted to launch unknown application: {app_name}")
                return True, f"Attempted to launch {app_name}"
        
        except Exception as e:
            # Record the failed launch
            self.launch_history.append({
                "app": app_name,
                "timestamp": datetime.datetime.now().isoformat(),
                "success": False,
                "error": str(e)
            })
            
            logger.error(f"Error launching {app_name}: {e}")
            return False, f"Failed to launch {app_name}: {str(e)}"
    
    def open_website(self, url, browser=None):
        try:
            # Add http:// if not present
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            if browser:
                browser = browser.lower()
                if browser in self.app_paths:
                    success, message = self.launch_app(browser)
                    if success:
                        # Wait a moment for the browser to start
                        time.sleep(1)
                        webbrowser.open(url)
                    else:
                        return False, f"Failed to open {browser}: {message}"
                else:
                    return False, f"Browser {browser} is not supported"
            else:
                # Use default browser
                webbrowser.open(url)
            
            logger.info(f"Opened website: {url}")
            return True, f"Opened {url} successfully"
        except Exception as e:
            logger.error(f"Error opening website {url}: {e}")
            return False, f"Failed to open {url}: {str(e)}"
    
    def search_web(self, query, browser=None):
        try:
            # Format the query for a URL
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            
            return self.open_website(search_url, browser)
        except Exception as e:
            logger.error(f"Error searching the web: {e}")
            return False, f"Failed to search the web: {str(e)}"
    
    def get_launch_history(self, limit=10):
        return self.launch_history[-limit:] if self.launch_history else []

class LearningSystem:
    def __init__(self):
        self.command_patterns = {}
        self.load_learning_data()
    
    def load_learning_data(self):
        try:
            if os.path.exists('learning_data.json'):
                with open('learning_data.json', 'r') as f:
                    self.command_patterns = json.load(f)
            logger.info("Loaded learning data")
        except Exception as e:
            logger.error(f"Error loading learning data: {e}")
    
    def save_learning_data(self):
        try:
            with open('learning_data.json', 'w') as f:
                json.dump(self.command_patterns, f)
            logger.info("Saved learning data")
        except Exception as e:
            logger.error(f"Error saving learning data: {e}")
    
    def learn_from_command(self, command, command_type, success):
        # Extract keywords from command
        words = command.lower().split()
        
        # Update command patterns
        if command_type not in self.command_patterns:
            self.command_patterns[command_type] = {
                "keywords": {},
                "total_uses": 0,
                "successful_uses": 0
            }
        
        self.command_patterns[command_type]["total_uses"] += 1
        if success:
            self.command_patterns[command_type]["successful_uses"] += 1
        
        # Update keyword frequencies
        for word in words:
            if len(word) > 2:  # Ignore very short words
                if word in self.command_patterns[command_type]["keywords"]:
                    self.command_patterns[command_type]["keywords"][word] += 1
                else:
                    self.command_patterns[command_type]["keywords"][word] = 1
        
        # Save the updated learning data
        self.save_learning_data()
    
    def predict_command_type(self, command):
        command = command.lower()
        words = command.split()
        
        best_match = None
        highest_score = 0
        
        for cmd_type, data in self.command_patterns.items():
            score = 0
            for word in words:
                if len(word) > 2 and word in data["keywords"]:
                    score += data["keywords"][word]
            
            # Normalize by total uses
            if data["total_uses"] > 0:
                score = score / data["total_uses"]
            
            if score > highest_score:
                highest_score = score
                best_match = cmd_type
        
        # Only return a prediction if the score is significant
        if highest_score > 0.1:
            return best_match
        return None
    
    def get_command_suggestions(self, partial_command, limit=3):
        partial_command = partial_command.lower()
        suggestions = []
        
        # Simple suggestion based on keyword matching
        for cmd_type, data in self.command_patterns.items():
            for keyword in data["keywords"]:
                if keyword.startswith(partial_command) and cmd_type not in suggestions:
                    suggestions.append(cmd_type)
                    break
            
            if len(suggestions) >= limit:
                break
        
        return suggestions

class CircularProgressBar(tk.Canvas):
    def __init__(self, parent, width, height, progress=0, fg_color="#00BFFF", bg_color="#1E1E1E", **kwargs):
        super().__init__(parent, width=width, height=height, bg=bg_color, highlightthickness=0, **kwargs)
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.width = width
        self.height = height
        self.progress = progress
        self.draw()
    
    def draw(self):
        self.delete("progress")
        
        # Calculate dimensions
        padding = 10
        x0 = padding
        y0 = padding
        x1 = self.width - padding
        y1 = self.height - padding
        
        # Draw background circle
        self.create_oval(x0, y0, x1, y1, fill=self.bg_color, outline="", tags="progress")
        
        # Draw progress arc
        start = 90
        extent = -self.progress * 360
        
        if self.progress > 0:
            self.create_arc(x0, y0, x1, y1, start=start, extent=extent, 
                           style=tk.ARC, outline=self.fg_color, width=4, tags="progress")
        
        # Draw text
        percentage = int(self.progress * 100)
        self.create_text(self.width/2, self.height/2, text=f"{percentage}%", 
                        fill=self.fg_color, font=("Arial", 12, "bold"), tags="progress")
    
    def set_progress(self, progress):
        self.progress = progress
        self.draw()

class VoiceVisualizer(tk.Canvas):
    def __init__(self, parent, width, height, bg_color="#1E1E1E", fg_color="#00BFFF", **kwargs):
        super().__init__(parent, width=width, height=height, bg=bg_color, highlightthickness=0, **kwargs)
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.bars = 20
        self.bar_width = (width - (self.bars + 1) * 2) / self.bars
        self.amplitudes = [0] * self.bars
        self.draw()
    
    def draw(self):
        self.delete("all")
        
        # Draw background
        self.create_rectangle(0, 0, self.width, self.height, fill=self.bg_color, outline="")
        
        # Draw bars
        for i in range(self.bars):
            x = i * (self.bar_width + 2) + 2
            y_center = self.height / 2
            amplitude = self.amplitudes[i] * (self.height / 2 - 10)
            
            # Draw bar
            self.create_rectangle(
                x, y_center - amplitude,
                x + self.bar_width, y_center + amplitude,
                fill=self.fg_color, outline=""
            )
    
    def update_visualization(self, audio_data=None):
        if audio_data is not None:
            # Process audio data to get amplitudes
            # This is a simplified version - in a real app, you'd process the actual audio
            chunk_size = len(audio_data) // self.bars
            new_amplitudes = []
            
            for i in range(self.bars):
                start = i * chunk_size
                end = start + chunk_size
                chunk = audio_data[start:end]
                amplitude = min(1.0, abs(np.mean(chunk)) / 32768)  # Normalize to 0-1
                new_amplitudes.append(amplitude)
            
            self.amplitudes = new_amplitudes
        else:
            # Generate random amplitudes for demo purposes
            self.amplitudes = [random.random() * 0.8 for _ in range(self.bars)]
        
        self.draw()

class HolographicDisplay(tk.Canvas):
    def __init__(self, parent, width, height, bg_color="#1E1E1E", fg_color="#00BFFF", **kwargs):
        super().__init__(parent, width=width, height=height, bg=bg_color, highlightthickness=0, **kwargs)
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.rings = 3
        self.points = 100
        self.rotation = 0
        self.draw()
    
    def draw(self):
        self.delete("all")
        
        # Draw background
        self.create_rectangle(0, 0, self.width, self.height, fill=self.bg_color, outline="")
        
        # Draw holographic rings
        center_x = self.width / 2
        center_y = self.height / 2
        
        for ring in range(self.rings):
            radius = (ring + 1) * (min(self.width, self.height) / (2 * (self.rings + 1)))
            
            # Draw ring
            points = []
            for i in range(self.points):
                angle = 2 * np.pi * i / self.points + self.rotation
                x = center_x + radius * np.cos(angle)
                y = center_y + radius * np.sin(angle)
                points.extend([x, y])
            
            # Create polygon with points
            if len(points) >= 4:  # Need at least 2 points (4 coordinates)
                self.create_polygon(points, outline=self.fg_color, fill="", width=1)
        
        # Draw intersecting lines
        for i in range(4):
            angle = np.pi * i / 4 + self.rotation
            x1 = center_x + (self.width / 2) * np.cos(angle)
            y1 = center_y + (self.height / 2) * np.sin(angle)
            x2 = center_x + (self.width / 2) * np.cos(angle + np.pi)
            y2 = center_y + (self.height / 2) * np.sin(angle + np.pi)
            
            self.create_line(x1, y1, x2, y2, fill=self.fg_color, width=1)
    
    def rotate(self, angle):
        self.rotation += angle
        self.draw()
    
    def animate(self):
        self.rotate(0.02)
        self.after(50, self.animate)

class JarvisAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("J.A.R.V.I.S. Assistant")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1E1E1E")
        
        # Set custom theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Initialize components
        self.profile_manager = ProfileManager()
        self.app_launcher = AppLauncher()
        self.learning_system = LearningSystem()
        self.telegram = TelegramIntegration()
        
        # Initialize speech recognition and text-to-speech engines
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()
        self.voices = self.engine.getProperty('voices')
        self.engine.setProperty('voice', self.voices[0].id)  # Male voice for Jarvis
        self.engine.setProperty('rate', 180)  # Speed of speech
        
        # Listening state
        self.is_listening = 180 # Speed of speech
        
        # Listening state
        self.is_listening = False
        
        # Error handling state
        self.error_count = 0
        self.last_error_time = None
        
        # Authentication state
        self.authenticated = False
        
        # Command handlers
        self.command_handlers = {
            "message": self.handle_message,
            "call": self.handle_call,
            "alarm": self.handle_alarm,
            "reminder": self.handle_reminder,
            "timer": self.handle_timer,
            "todo": self.handle_todo,
            "weather": self.handle_weather,
            "news": self.handle_news,
            "music": self.handle_music,
            "open": self.handle_open_app,
            "launch": self.handle_open_app,
            "start": self.handle_open_app,
            "run": self.handle_open_app,
            "spotify": self.handle_spotify,
            "chrome": self.handle_chrome,
            "firefox": self.handle_firefox,
            "telegram": self.handle_telegram,
            "browser": self.handle_chrome,
            "search": self.handle_search,
            "google": self.handle_search,
            "find": self.handle_search,
            "look up": self.handle_search,
            "contact": self.handle_contact,
            "profile": self.handle_profile,
            "feedback": self.handle_feedback,
            "help": self.handle_help,
            "exit": self.handle_exit,
            "authenticate": self.handle_authenticate,
            "login": self.handle_authenticate,
            "logout": self.handle_logout
        }
        
        # Create GUI elements
        self.create_widgets()
        
        # Animation timer
        self.animation_timer = None
        
        # Check for existing profiles and prompt to create or select one
        self.check_profiles()
    
    def check_profiles(self):
        profile_names = self.profile_manager.get_profile_names()
        
        if not profile_names:
            self.root.after(500, self.prompt_create_profile)
        else:
            self.root.after(500, lambda: self.prompt_select_profile(profile_names))
    
    def prompt_create_profile(self):
        name = simpledialog.askstring("Create Profile", "Please enter your name:", parent=self.root)
        if name:
            location = simpledialog.askstring("Create Profile", "Please enter your location (optional):", parent=self.root)
            self.profile_manager.create_profile(name, location or "")
            self.profile_manager.set_current_profile(name)
            self.update_profile_display()
            self.speak(f"Welcome, {name}! I am Jarvis, your personal assistant. How may I assist you today?")
        else:
            # Create a default profile if user cancels
            self.profile_manager.create_profile("User")
            self.profile_manager.set_current_profile("User")
            self.update_profile_display()
            self.speak("Welcome! I am Jarvis, your personal assistant. How may I assist you today?")
    
    def prompt_select_profile(self, profile_names):
        if len(profile_names) == 1:
            # If there's only one profile, use it automatically
            self.profile_manager.set_current_profile(profile_names[0])
            self.update_profile_display()
            profile = self.profile_manager.get_current_profile()
            self.speak(f"Welcome back, {profile.name}! How may I assist you today?")
        else:
            # Create a Jarvis-styled profile selection dialog
            select_window = tk.Toplevel(self.root)
            select_window.title("Select Profile")
            select_window.geometry("400x500")
            select_window.configure(bg="#1E1E1E")
            
            tk.Label(select_window, text="Select Your Profile", font=("Arial", 16, "bold"), 
                    bg="#1E1E1E", fg="#00BFFF").pack(pady=20)
            
            profile_frame = tk.Frame(select_window, bg="#1E1E1E")
            profile_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            profile_var = tk.StringVar()
            
            for i, name in enumerate(profile_names):
                profile_button = ctk.CTkButton(
                    profile_frame, 
                    text=name,
                    command=lambda n=name: profile_var.set(n),
                    fg_color="#00BFFF",
                    text_color="#FFFFFF",
                    hover_color="#0080FF",
                    height=40,
                    corner_radius=10
                )
                profile_button.pack(fill=tk.X, pady=5)
            
            def confirm_selection():
                selected = profile_var.get()
                if selected:
                    self.profile_manager.set_current_profile(selected)
                    self.update_profile_display()
                    profile = self.profile_manager.get_current_profile()
                    self.speak(f"Welcome back, {profile.name}! How may I assist you today?")
                else:
                    # If no selection, use the first profile
                    self.profile_manager.set_current_profile(profile_names[0])
                    self.update_profile_display()
                    profile = self.profile_manager.get_current_profile()
                    self.speak(f"Welcome back, {profile.name}! How may I assist you today?")
                select_window.destroy()
            
            def create_new():
                select_window.destroy()
                self.prompt_create_profile()
            
            button_frame = tk.Frame(select_window, bg="#1E1E1E")
            button_frame.pack(fill=tk.X, padx=20, pady=20)
            
            ctk.CTkButton(
                button_frame, 
                text="Confirm",
                command=confirm_selection,
                fg_color="#00BFFF",
                text_color="#FFFFFF",
                hover_color="#0080FF",
                height=40,
                corner_radius=10
            ).pack(fill=tk.X, pady=5)
            
            ctk.CTkButton(
                button_frame, 
                text="Create New Profile",
                command=create_new,
                fg_color="#333333",
                text_color="#FFFFFF",
                hover_color="#444444",
                height=40,
                corner_radius=10
            ).pack(fill=tk.X, pady=5)
    
    def update_profile_display(self):
        profile = self.profile_manager.get_current_profile()
        if profile:
            self.profile_label.config(text=f"Profile: {profile.name}")
            
            # Update voice settings based on profile preferences
            voice_gender = profile.preferences.get("voice_gender", "Male")
            voice_idx = 0 if voice_gender == "Male" else 1
            self.engine.setProperty('voice', self.voices[voice_idx].id)
            
            voice_speed = profile.preferences.get("voice_speed", 180)
            self.engine.setProperty('rate', voice_speed)
            
            # Update authentication status
            self.update_auth_status(profile.is_authenticated())
    
    def update_auth_status(self, is_authenticated):
        if is_authenticated:
            self.auth_status.config(text="Authenticated", fg="#4CAF50")
            self.authenticated = True
        else:
            self.auth_status.config(text="Not Authenticated", fg="#F44336")
            self.authenticated = False
    
    def create_widgets(self):
        # Main container
        self.main_container = tk.Frame(self.root, bg="#1E1E1E")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Top bar with Jarvis logo, profile, and status
        top_frame = tk.Frame(self.main_container, bg="#1E1E1E", height=80)
        top_frame.pack(fill=tk.X, pady=10)
        
        # Jarvis logo/title
        title_frame = tk.Frame(top_frame, bg="#1E1E1E")
        title_frame.pack(side=tk.LEFT, padx=20)
        
        self.assistant_name = tk.Label(title_frame, text="J.A.R.V.I.S.", font=("Arial", 28, "bold"), 
                                     bg="#1E1E1E", fg="#00BFFF")
        self.assistant_name.pack(side=tk.TOP)
        
        tk.Label(title_frame, text="Just A Rather Very Intelligent System", font=("Arial", 10), 
               bg="#1E1E1E", fg="#AAAAAA").pack(side=tk.TOP)
        
        # Status indicators
        status_frame = tk.Frame(top_frame, bg="#1E1E1E")
        status_frame.pack(side=tk.RIGHT, padx=20)
        
        self.profile_label = tk.Label(status_frame, text="Profile: None", font=("Arial", 12), 
                                    bg="#1E1E1E", fg="#FFFFFF")
        self.profile_label.pack(side=tk.TOP, anchor=tk.E)
        
        status_indicators = tk.Frame(status_frame, bg="#1E1E1E")
        status_indicators.pack(side=tk.TOP, anchor=tk.E)
        
        self.status_label = tk.Label(status_indicators, text="Ready", font=("Arial", 10), 
                                   fg="#4CAF50", bg="#1E1E1E")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.auth_status = tk.Label(status_indicators, text="Not Authenticated", font=("Arial", 10), 
                                  fg="#F44336", bg="#1E1E1E")
        self.auth_status.pack(side=tk.LEFT, padx=5)
        
        # Main content area with split layout
        content_frame = tk.Frame(self.main_container, bg="#1E1E1E")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left panel with visualizations
        left_panel = tk.Frame(content_frame, bg="#1E1E1E", width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Holographic display
        holo_frame = tk.Frame(left_panel, bg="#1E1E1E")
        holo_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(holo_frame, text="System Status", font=("Arial", 12, "bold"), 
               bg="#1E1E1E", fg="#00BFFF").pack(anchor=tk.W)
        
        self.holo_display = HolographicDisplay(holo_frame, 280, 200)
        self.holo_display.pack(pady=5)
        self.holo_display.animate()  # Start animation
        
        # Voice visualizer
        voice_frame = tk.Frame(left_panel, bg="#1E1E1E")
        voice_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(voice_frame, text="Voice Input", font=("Arial", 12, "bold"), 
               bg="#1E1E1E", fg="#00BFFF").pack(anchor=tk.W)
        
        self.voice_visualizer = VoiceVisualizer(voice_frame, 280, 100)
        self.voice_visualizer.pack(pady=5)
        
        # System metrics
        metrics_frame = tk.Frame(left_panel, bg="#1E1E1E")
        metrics_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(metrics_frame, text="System Metrics", font=("Arial", 12, "bold"), 
               bg="#1E1E1E", fg="#00BFFF").pack(anchor=tk.W)
        
        metrics_grid = tk.Frame(metrics_frame, bg="#1E1E1E")
        metrics_grid.pack(fill=tk.X, pady=5)
        
        # CPU usage
        cpu_frame = tk.Frame(metrics_grid, bg="#1E1E1E")
        cpu_frame.grid(row=0, column=0, padx=5, pady=5)
        
        tk.Label(cpu_frame, text="CPU", font=("Arial", 10), 
               bg="#1E1E1E", fg="#FFFFFF").pack()
        
        self.cpu_progress = CircularProgressBar(cpu_frame, 80, 80, progress=0.45)
        self.cpu_progress.pack()
        
        # Memory usage
        mem_frame = tk.Frame(metrics_grid, bg="#1E1E1E")
        mem_frame.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(mem_frame, text="Memory", font=("Arial", 10), 
               bg="#1E1E1E", fg="#FFFFFF").pack()
        
        self.mem_progress = CircularProgressBar(mem_frame, 80, 80, progress=0.65)
        self.mem_progress.pack()
        
        # Network usage
        net_frame = tk.Frame(metrics_grid, bg="#1E1E1E")
        net_frame.grid(row=1, column=0, padx=5, pady=5)
        
        tk.Label(net_frame, text="Network", font=("Arial", 10), 
               bg="#1E1E1E", fg="#FFFFFF").pack()
        
        self.net_progress = CircularProgressBar(net_frame, 80, 80, progress=0.30)
        self.net_progress.pack()
        
        # Battery usage
        bat_frame = tk.Frame(metrics_grid, bg="#1E1E1E")
        bat_frame.grid(row=1, column=1, padx=5, pady=5)
        
        tk.Label(bat_frame, text="Battery", font=("Arial", 10), 
               bg="#1E1E1E", fg="#FFFFFF").pack()
        
        self.bat_progress = CircularProgressBar(bat_frame, 80, 80, progress=0.80)
        self.bat_progress.pack()
        
        # Right panel with conversation and controls
        right_panel = tk.Frame(content_frame, bg="#1E1E1E")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Conversation display
        conversation_frame = tk.Frame(right_panel, bg="#1E1E1E")
        conversation_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        tk.Label(conversation_frame, text="Conversation", font=("Arial", 12, "bold"), 
               bg="#1E1E1E", fg="#00BFFF").pack(anchor=tk.W)
        
        self.conversation = scrolledtext.ScrolledText(
            conversation_frame, 
            wrap=tk.WORD, 
            font=("Arial", 12), 
            bg="#2A2A2A", 
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            height=15
        )
        self.conversation.pack(fill=tk.BOTH, expand=True, pady=5)
        self.conversation.config(state=tk.DISABLED)
        
        # Suggestion bar
        suggestion_frame = tk.Frame(right_panel, bg="#1E1E1E")
        suggestion_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(suggestion_frame, text="Suggestions:", font=("Arial", 10), 
               bg="#1E1E1E", fg="#AAAAAA").pack(side=tk.LEFT)
        
        self.suggestion_buttons = []
        for i in range(3):
            btn = ctk.CTkButton(
                suggestion_frame,
                text="",
                fg_color="#333333",
                text_color="#FFFFFF",
                hover_color="#444444",
                height=30,
                width=150,
                corner_radius=15,
                state="disabled"
            )
            btn.pack(side=tk.LEFT, padx=5)
            self.suggestion_buttons.append(btn)
        
        # User input frame
        input_frame = tk.Frame(right_panel, bg="#1E1E1E")
        input_frame.pack(fill=tk.X, pady=10)
        
        self.user_input = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type your command here...",
            height=40,
            corner_radius=20,
            fg_color="#2A2A2A",
            text_color="#FFFFFF",
            placeholder_text_color="#AAAAAA"
        )
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.user_input.bind("<Return>", lambda event: self.process_text_input())
        self.user_input.bind("<KeyRelease>", self.on_input_change)
        
        self.send_button = ctk.CTkButton(
            input_frame,
            text="Send",
            command=self.process_text_input,
            fg_color="#00BFFF",
            text_color="#FFFFFF",
            hover_color="#0080FF",
            height=40,
            width=80,
            corner_radius=20
        )
        self.send_button.pack(side=tk.RIGHT)
        
        # Voice button
        voice_button_frame = tk.Frame(right_panel, bg="#1E1E1E")
        voice_button_frame.pack(fill=tk.X, pady=10)
        
        self.voice_button = ctk.CTkButton(
            voice_button_frame,
            text="🎤 Activate Voice Recognition",
            command=self.toggle_listening,
            fg_color="#00BFFF",
            text_color="#FFFFFF",
            hover_color="#0080FF",
            height=50,
            corner_radius=25
        )
        self.voice_button.pack(fill=tk.X)
        
        # Feature buttons
        feature_frame = tk.Frame(right_panel, bg="#1E1E1E")
        feature_frame.pack(fill=tk.X, pady=10)
        
        features = [
            ("Message", "message"), 
            ("Search", "search"), 
            ("Open App", "open"), 
            ("Weather", "weather"), 
            ("Contacts", "contact"), 
            ("Help", "help")
        ]
        
        for label, cmd in features:
            btn = ctk.CTkButton(
                feature_frame,
                text=label,
                command=lambda c=cmd: self.quick_feature(c),
                fg_color="#333333",
                text_color="#FFFFFF",
                hover_color="#444444",
                height=35,
                width=100,
                corner_radius=17
            )
            btn.pack(side=tk.LEFT, padx=5)
        
        # Settings and feedback buttons
        control_frame = tk.Frame(feature_frame, bg="#1E1E1E")
        control_frame.pack(side=tk.RIGHT)
        
        self.feedback_button = ctk.CTkButton(
            control_frame,
            text="Feedback",
            command=self.show_feedback_dialog,
            fg_color="#FFC107",
            text_color="#000000",
            hover_color="#FFD54F",
            height=35,
            width=100,
            corner_radius=17
        )
        self.feedback_button.pack(side=tk.LEFT, padx=5)
        
        self.settings_button = ctk.CTkButton(
            control_frame,
            text="⚙️ Settings",
            command=self.open_settings,
            fg_color="#333333",
            text_color="#FFFFFF",
            hover_color="#444444",
            height=35,
            width=100,
            corner_radius=17
        )
        self.settings_button.pack(side=tk.LEFT, padx=5)
        
        # Status bar
        status_bar = tk.Frame(self.main_container, bg="#2A2A2A", height=25)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.error_status = tk.Label(status_bar, text="No errors", font=("Arial", 8), 
                                   fg="#4CAF50", bg="#2A2A2A")
        self.error_status.pack(side=tk.LEFT, padx=5)
        
        version_label = tk.Label(status_bar, text="v3.0", font=("Arial", 8), 
                               bg="#2A2A2A", fg="#AAAAAA")
        version_label.pack(side=tk.RIGHT, padx=5)
        
        # Start periodic updates for visualizations
        self.start_visualization_updates()
    
    def start_visualization_updates(self):
        # Update visualizations periodically
        def update_visualizations():
            # Update voice visualizer with random data (for demo)
            self.voice_visualizer.update_visualization()
            
            # Update system metrics with random data (for demo)
            self.cpu_progress.set_progress(random.random() * 0.8 + 0.1)
            self.mem_progress.set_progress(random.random() * 0.6 + 0.2)
            self.net_progress.set_progress(random.random() * 0.5 + 0.1)
            self.bat_progress.set_progress(random.random() * 0.3 + 0.7)
            
            # Schedule next update
            self.root.after(1000, update_visualizations)
        
        # Start the updates
        update_visualizations()
    
    def on_input_change(self, event):
        # Update suggestions based on current input
        current_text = self.user_input.get().strip()
        if current_text:
            suggestions = self.learning_system.get_command_suggestions(current_text)
            
            # Update suggestion buttons
            for i, btn in enumerate(self.suggestion_buttons):
                if i < len(suggestions):
                    btn.configure(text=suggestions[i], state="normal", 
                                 command=lambda s=suggestions[i]: self.use_suggestion(s))
                else:
                    btn.configure(text="", state="disabled")
        else:
            # Clear suggestions if input is empty
            for btn in self.suggestion_buttons:
                btn.configure(text="", state="disabled")
    
    def use_suggestion(self, suggestion):
        # When a suggestion button is clicked
        self.user_input.delete(0, tk.END)
        self.user_input.insert(0, suggestion)
        self.process_text_input()
    
    def update_conversation(self, speaker, text):
        self.conversation.config(state=tk.NORMAL)
        timestamp = datetime.datetime.now().strftime("%H:%M")
        
        if speaker == "user":
            self.conversation.insert(tk.END, f"\n[{timestamp}] You: ", "user_tag")
            self.conversation.insert(tk.END, f"{text}\n", "user_text")
        elif speaker == "assistant":
            self.conversation.insert(tk.END, f"\n[{timestamp}] J.A.R.V.I.S.: ", "assistant_tag")
            self.conversation.insert(tk.END, f"{text}\n", "assistant_text")
        elif speaker == "error":
            self.conversation.insert(tk.END, f"\n[{timestamp}] Error: ", "error_tag")
            self.conversation.insert(tk.END, f"{text}\n", "error_text")
        elif speaker == "system":
            self.conversation.insert(tk.END, f"\n[{timestamp}] System: ", "system_tag")
            self.conversation.insert(tk.END, f"{text}\n", "system_text")
        
        self.conversation.tag_config("user_tag", foreground="#00BFFF", font=("Arial", 12, "bold"))
        self.conversation.tag_config("user_text", foreground="#FFFFFF", font=("Arial", 12))
        self.conversation.tag_config("assistant_tag", foreground="#4CAF50", font=("Arial", 12, "bold"))
        self.conversation.tag_config("assistant_text", foreground="#FFFFFF", font=("Arial", 12))
        self.conversation.tag_config("error_tag", foreground="#F44336", font=("Arial", 12, "bold"))
        self.conversation.tag_config("error_text", foreground="#F44336", font=("Arial", 12))
        self.conversation.tag_config("system_tag", foreground="#9E9E9E", font=("Arial", 12, "bold"))
        self.conversation.tag_config("system_text", foreground="#9E9E9E", font=("Arial", 12))
        
        self.conversation.see(tk.END)
        self.conversation.config(state=tk.DISABLED)
    
    def toggle_listening(self):
        if self.is_listening:
            self.is_listening = False
            self.voice_button.configure(text="🎤 Activate Voice Recognition", fg_color="#00BFFF")
            self.status_label.config(text="Ready", fg="#4CAF50")
        else:
            self.is_listening = True
            self.voice_button.configure(text="⏹️ Stop Listening", fg_color="#F44336")
            self.status_label.config(text="Listening...", fg="#F44336")
            threading.Thread(target=self.listen_for_command, daemon=True).start()
    
    def listen_for_command(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            while self.is_listening:
                try:
                    self.status_label.config(text="Listening...", fg="#F44336")
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    
                    # Update voice visualizer with actual audio data
                    audio_data = np.frombuffer(audio.frame_data, dtype=np.int16)
                    self.voice_visualizer.update_visualization(audio_data)
                    
                    self.status_label.config(text="Processing...", fg="#FFC107")
                    
                    text = self.recognizer.recognize_google(audio)
                    if text.lower() in ["stop listening", "stop", "exit"]:
                        self.toggle_listening()
                        break
                    
                    self.user_input.delete(0, tk.END)
                    self.user_input.insert(0, text)
                    self.update_conversation("user", text)
                    
                    # Add to profile's command history if a profile is active
                    profile = self.profile_manager.get_current_profile()
                    if profile:
                        profile.add_command_to_history(text)
                    
                    self.process_command(text)
                    
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    self.status_label.config(text="Didn't catch that", fg="#FFC107")
                    continue
                except Exception as e:
                    self.handle_error(e, "Speech recognition error")
                    continue
            
            self.status_label.config(text="Ready", fg="#4CAF50")
    
    def process_text_input(self):
        text = self.user_input.get().strip()
        if text:
            self.update_conversation("user", text)
            self.user_input.delete(0, tk.END)
            
            # Add to profile's command history if a profile is active
            profile = self.profile_manager.get_current_profile()
            if profile:
                profile.add_command_to_history(text)
            
            self.process_command(text)
    
    def process_command(self, text):
        text = text.lower()
        
        # Use learning system to predict command type
        predicted_type = self.learning_system.predict_command_type(text)
        
        # Check for command keywords
        command_type = None
        for keyword in self.command_handlers.keys():
            if keyword in text:
                command_type = keyword
                break
        
        # If no explicit keyword found, use the predicted type
        if not command_type and predicted_type:
            command_type = predicted_type
        
        success = False
        try:
            if command_type:
                # Check if authentication is required for this command
                auth_required = command_type in ["message", "contact", "telegram", "profile"]
                
                # If authentication is required and user is not authenticated
                if auth_required and not self.authenticated:
                    profile = self.profile_manager.get_current_profile()
                    if profile and not profile.is_authenticated():
                        response = "Authentication required. Please authenticate first by saying 'login' or 'authenticate'."
                        self.update_conversation("assistant", response)
                        self.speak(response)
                        return
                
                # Execute the appropriate handler
                response = self.command_handlers[command_type](text)
                
                # Update profile's frequent commands
                profile = self.profile_manager.get_current_profile()
                if profile:
                    profile.update_frequent_commands(command_type)
                
                # Learn from this command
                self.learning_system.learn_from_command(text, command_type, True)
                success = True
            else:
                # General conversation
                response = self.general_conversation(text)
        except Exception as e:
            self.handle_error(e, f"Error processing command: {text}")
            response = f"I'm sorry, I encountered an error while processing your request. Please try again."
            success = False
        
        # Update conversation and speak response
        self.update_conversation("assistant", response)
        self.speak(response)
        
        # Update profile's learning data
        profile = self.profile_manager.get_current_profile()
        if profile:
            profile.update_learning_data(text, response, success)
            self.profile_manager.save_profile(profile)
    
    def speak(self, text):
        def speak_thread():
            try:
                self.status_label.config(text="Speaking...", fg="#2196F3")
                self.engine.say(text)
                self.engine.runAndWait()
                self.status_label.config(text="Ready", fg="#4CAF50")
            except Exception as e:
                self.handle_error(e, "Text-to-speech error")
        
        threading.Thread(target=speak_thread, daemon=True).start()
    
    def quick_feature(self, feature):
        prompts = {
            "message": "Who would you like to message?",
            "search": "What would you like to search for?",
            "open": "Which application would you like to open?",
            "weather": "Would you like to know the weather for today?",
            "contact": "What would you like to do with your contacts?",
            "help": "Here are some things I can help you with:\n- Send messages via Telegram\n- Search the web using Chrome or Firefox\n- Open applications like Spotify, Chrome, and Telegram\n- Check weather\n- Manage your contacts\n- Set alarms and reminders"
        }
        
      

    
    def handle_error(self, error, context=""):
        # Log the error
        logger.error(f"{context}: {str(error)}")
        
        # Update error count and time
        self.error_count += 1
        self.last_error_time = datetime.datetime.now()
        
        # Update error status in UI
        self.error_status.config(text=f"Last error: {str(error)[:30]}...", fg="#F44336")
        
        # If too many errors in a short time, suggest restart
        if self.error_count > 5:
            current_time = datetime.datetime.now()
            if self.last_error_time and (current_time - self.last_error_time).seconds < 60:
                self.update_conversation("error", "Multiple errors detected. Consider restarting the application.")
                self.error_count = 0
    
    def show_feedback_dialog(self):
        feedback_window = ctk.CTkToplevel(self.root)
        feedback_window.title("Provide Feedback")
        feedback_window.geometry("500x400")
        feedback_window.configure(fg_color="#1E1E1E")
        
        ctk.CTkLabel(feedback_window, text="Rate Your Experience", font=("Arial", 16, "bold")).pack(pady=20)
        
        # Rating scale
        rating_frame = ctk.CTkFrame(feedback_window, fg_color="#1E1E1E")
        rating_frame.pack(pady=10)
        
        rating_var = tk.IntVar(value=5)
        
        rating_scale = ctk.CTkFrame(rating_frame, fg_color="#1E1E1E")
        rating_scale.pack()
        
        for i in range(1, 6):
            ctk.CTkRadioButton(
                rating_scale, 
                text=str(i), 
                variable=rating_var, 
                value=i,
                fg_color="#00BFFF",
                border_color="#AAAAAA"
            ).pack(side=tk.LEFT, padx=15)
        
        ctk.CTkLabel(rating_frame, text="Poor", font=("Arial", 10)).place(x=20, y=30)
        ctk.CTkLabel(rating_frame, text="Excellent", font=("Arial", 10)).place(x=200, y=30)
        
        # Comments
        ctk.CTkLabel(feedback_window, text="Comments:", font=("Arial", 12)).pack(anchor=tk.W, padx=20, pady=(20, 5))
        
        comments = ctk.CTkTextbox(feedback_window, height=120, width=460)
        comments.pack(padx=20, pady=5)
        
        def submit_feedback():
            rating = rating_var.get()
            comment = comments.get("1.0", tk.END).strip()
            
            # Save feedback to profile
            profile = self.profile_manager.get_current_profile()
            if profile:
                profile.add_feedback(rating, comment)
                self.profile_manager.save_profile(profile)
            
            # Thank the user
            self.update_conversation("system", f"Thank you for your feedback! Rating: {rating}/5")
            feedback_window.destroy()
        
        ctk.CTkButton(
            feedback_window, 
            text="Submit Feedback", 
            command=submit_feedback,
            fg_color="#00BFFF",
            text_color="#FFFFFF",
            hover_color="#0080FF",
            height=40,
            corner_radius=20
        ).pack(pady=20)
    
    def open_settings(self):
        profile = self.profile_manager.get_current_profile()
        if not profile:
            messagebox.showinfo("Settings", "Please create a profile first.")
            return
        
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("J.A.R.V.I.S. Settings")
        settings_window.geometry("600x700")
        settings_window.configure(fg_color="#1E1E1E")
        
        ctk.CTkLabel(settings_window, text="J.A.R.V.I.S. Settings", font=("Arial", 20, "bold")).pack(pady=20)
        
        # Create tabview for settings categories
        tabview = ctk.CTkTabview(settings_window, width=560, height=600)
        tabview.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        # Add tabs
        tab_profile = tabview.add("Profile")
        tab_voice = tabview.add("Voice")
        tab_apps = tabview.add("Applications")
        tab_telegram = tabview.add("Telegram")
        tab_contacts = tabview.add("Contacts")
        tab_security = tabview.add("Security")
        
        # Profile settings
        profile_frame = ctk.CTkFrame(tab_profile, fg_color="#2A2A2A")
        profile_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(profile_frame, text="Profile Information", font=("Arial", 16, "bold")).pack(pady=10)
        
        # Name
        ctk.CTkLabel(profile_frame, text="Name:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        name_var = tk.StringVar(value=profile.name)
        name_entry = ctk.CTkEntry(profile_frame, textvariable=name_var, width=300)
        name_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Location
        ctk.CTkLabel(profile_frame, text="Location:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        location_var = tk.StringVar(value=profile.location)
        location_entry = ctk.CTkEntry(profile_frame, textvariable=location_var, width=300)
        location_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Voice settings
        voice_frame = ctk.CTkFrame(tab_voice, fg_color="#2A2A2A")
        voice_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(voice_frame, text="Voice Settings", font=("Arial", 16, "bold")).pack(pady=10)
        
        # Voice selection
        ctk.CTkLabel(voice_frame, text="Voice:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        voice_var = tk.StringVar(value=profile.preferences.get("voice_gender", "Male"))
        voice_dropdown = ctk.CTkComboBox(voice_frame, values=["Male", "Female"], variable=voice_var, width=300)
        voice_dropdown.pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Speed
        ctk.CTkLabel(voice_frame, text="Speed:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        speed_var = tk.IntVar(value=profile.preferences.get("voice_speed", 180))
        speed_slider = ctk.CTkSlider(voice_frame, from_=100, to=300, variable=speed_var, width=300)
        speed_slider.pack(anchor=tk.W, padx=20, pady=(0, 10))
        speed_value = ctk.CTkLabel(voice_frame, text=f"Value: {speed_var.get()}")
        speed_value.pack(anchor=tk.W, padx=20)
        
        def update_speed_label(value):
            speed_value.configure(text=f"Value: {int(value)}")
        
        speed_slider.configure(command=update_speed_label)
        
        # Applications settings
        apps_frame = ctk.CTkFrame(tab_apps, fg_color="#2A2A2A")
        apps_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(apps_frame, text="Favorite Applications", font=("Arial", 16, "bold")).pack(pady=10)
        
        favorite_apps = profile.get_favorite_apps()
        
        apps_list_frame = ctk.CTkFrame(apps_frame, fg_color="#2A2A2A")
        apps_list_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        
        apps_listbox = tk.Listbox(apps_list_frame, bg="#333333", fg="#FFFFFF", selectbackground="#00BFFF", height=10)
        apps_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        for app in favorite_apps:
            apps_listbox.insert(tk.END, app)
        
        apps_scrollbar = tk.Scrollbar(apps_list_frame)
        apps_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        apps_listbox.config(yscrollcommand=apps_scrollbar.set)
        apps_scrollbar.config(command=apps_listbox.yview)
        
        apps_buttons_frame = ctk.CTkFrame(apps_frame, fg_color="#2A2A2A")
        apps_buttons_frame.pack(padx=20, pady=10, fill=tk.X)
        
        def add_favorite_app():
            app = simpledialog.askstring("Add Favorite App", "Enter application name:", parent=settings_window)
            if app and app not in favorite_apps:
                apps_listbox.insert(tk.END, app)
                favorite_apps.append(app)
        
        def remove_favorite_app():
            selected = apps_listbox.curselection()
            if selected:
                app = apps_listbox.get(selected[0])
                apps_listbox.delete(selected[0])
                favorite_apps.remove(app)
        
        ctk.CTkButton(
            apps_buttons_frame, 
            text="Add", 
            command=add_favorite_app,
            fg_color="#00BFFF",
            text_color="#FFFFFF",
            hover_color="#0080FF",
            width=100
        ).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkButton(
            apps_buttons_frame, 
            text="Remove", 
            command=remove_favorite_app,
            fg_color="#F44336",
            text_color="#FFFFFF",
            hover_color="#D32F2F",
            width=100
        ).pack(side=tk.LEFT, padx=5)
        
        # Telegram settings
        telegram_frame = ctk.CTkFrame(tab_telegram, fg_color="#2A2A2A")
        telegram_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(telegram_frame, text="Telegram Integration", font=("Arial", 16, "bold")).pack(pady=10)
        
        # API ID
        ctk.CTkLabel(telegram_frame, text="API ID:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        api_id_var = tk.StringVar()
        api_id_entry = ctk.CTkEntry(telegram_frame, textvariable=api_id_var, width=300)
        api_id_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # API Hash
        ctk.CTkLabel(telegram_frame, text="API Hash:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        api_hash_var = tk.StringVar()
        api_hash_entry = ctk.CTkEntry(telegram_frame, textvariable=api_hash_var, width=300, show="*")
        api_hash_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Session name
        ctk.CTkLabel(telegram_frame, text="Session Name:").pack(anchor=tk.W, padx=20, pady=(10, 0))
        session_var = tk.StringVar(value=profile.telegram_session or "jarvis_telegram")
        session_entry = ctk.CTkEntry(telegram_frame, textvariable=session_var, width=300)
        session_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
        
        # Test connection button
        def test_telegram_connection():
            api_id = api_id_var.get().strip()
            api_hash = api_hash_var.get().strip()
            session = session_var.get().strip()
            
            if not api_id or not api_hash:
                messagebox.showerror("Error", "API ID and API Hash are required", parent=settings_window)
                return
            
            # Initialize Telegram client
            self.telegram = TelegramIntegration(api_id, api_hash)
            success = self.telegram.initialize(session)
            
            if success:
                messagebox.showinfo("Success", "Telegram connection successful!", parent=settings_window)
                profile.set_telegram_session(session)
            else:
                messagebox.showerror("Error", f"Telegram connection failed: {self.telegram.error_message}", parent=settings_window)
        
        ctk.CTkButton(
            telegram_frame, 
            text="Test Connection", 
            command=test_telegram_connection,
            fg_color="#00BFFF",
            text_color="#FFFFFF",
            hover_color="#0080FF",
            width=200
        ).pack(anchor=tk.W, padx=20, pady=10)
        
        # Contacts settings
        contacts_frame = ctk.CTkFrame(tab_contacts, fg_color="#2A2A2A")
        contacts_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(contacts_frame, text="Contacts", font=("Arial", 16, "bold")).pack(pady=10)
        
        contacts = profile.get_all_contacts()
        
        contacts_list_frame = ctk.CTkFrame(contacts_frame, fg_color="#2A2A2A")
        contacts_list_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        
        contacts_listbox = tk.Listbox(contacts_list_frame, bg="#333333", fg="#FFFFFF", selectbackground="#00BFFF", height=10)
        contacts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        for contact in contacts:
            contacts_listbox.insert(tk.END, contact.name)
        
        contacts_scrollbar = tk.Scrollbar(contacts_list_frame)
        contacts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        contacts_listbox.config(yscrollcommand=contacts_scrollbar.set)
        contacts_scrollbar.config(command=contacts_listbox.yview)
        
        contacts_buttons_frame = ctk.CTkFrame(contacts_frame, fg_color="#2A2A2A")
        contacts_buttons_frame.pack(padx=20, pady=10, fill=tk.X)
        
        def add_contact():
            # Create a contact dialog
            contact_dialog = ctk.CTkToplevel(settings_window)
            contact_dialog.title("Add Contact")
            contact_dialog.geometry("400x300")
            contact_dialog.configure(fg_color="#1E1E1E")
            
            ctk.CTkLabel(contact_dialog, text="Add New Contact", font=("Arial", 16, "bold")).pack(pady=10)
            
            # Name
            ctk.CTkLabel(contact_dialog, text="Name:").pack(anchor=tk.W, padx=20, pady=(10, 0))
            name_var = tk.StringVar()
            name_entry = ctk.CTkEntry(contact_dialog, textvariable=name_var, width=300)
            name_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
            
            # Telegram username
            ctk.CTkLabel(contact_dialog, text="Telegram Username:").pack(anchor=tk.W, padx=20, pady=(10, 0))
            telegram_var = tk.StringVar()
            telegram_entry = ctk.CTkEntry(contact_dialog, textvariable=telegram_var, width=300)
            telegram_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
            
            # Phone
            ctk.CTkLabel(contact_dialog, text="Phone:").pack(anchor=tk.W, padx=20, pady=(10, 0))
            phone_var = tk.StringVar()
            phone_entry = ctk.CTkEntry(contact_dialog, textvariable=phone_var, width=300)
            phone_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
            
            def save_contact():
                name = name_var.get().strip()
                telegram = telegram_var.get().strip()
                phone = phone_var.get().strip()
                
                if not name:
                    messagebox.showerror("Error", "Name is required", parent=contact_dialog)
                    return
                
                # Create and add contact
                contact = Contact(name, telegram, phone)
                profile.add_contact(contact)
                
                # Update listbox
                contacts_listbox.insert(tk.END, name)
                
                contact_dialog.destroy()
            
            ctk.CTkButton(
                contact_dialog, 
                text="Save Contact", 
                command=save_contact,
                fg_color="#00BFFF",
                text_color="#FFFFFF",
                hover_color="#0080FF",
                width=200
            ).pack(pady=20)
        
        def edit_contact():
            selected = contacts_listbox.curselection()
            if not selected:
                messagebox.showinfo("Info", "Please select a contact to edit", parent=settings_window)
                return
            
            contact_name = contacts_listbox.get(selected[0])
            contact = profile.get_contact(contact_name)
            
            if not contact:
                messagebox.showerror("Error", "Contact not found", parent=settings_window)
                return
            
            # Create an edit dialog
            edit_dialog = ctk.CTkToplevel(settings_window)
            edit_dialog.title("Edit Contact")
            edit_dialog.geometry("400x300")
            edit_dialog.configure(fg_color="#1E1E1E")
            
            ctk.CTkLabel(edit_dialog, text="Edit Contact", font=("Arial", 16, "bold")).pack(pady=10)
            
            # Name
            ctk.CTkLabel(edit_dialog, text="Name:").pack(anchor=tk.W, padx=20, pady=(10, 0))
            name_var = tk.StringVar(value=contact.name)
            name_entry = ctk.CTkEntry(edit_dialog, textvariable=name_var, width=300)
            name_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
            
            # Telegram username
            ctk.CTkLabel(edit_dialog, text="Telegram Username:").pack(anchor=tk.W, padx=20, pady=(10, 0))
            telegram_var = tk.StringVar(value=contact.telegram_username or "")
            telegram_entry = ctk.CTkEntry(edit_dialog, textvariable=telegram_var, width=300)
            telegram_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
            
            # Phone
            ctk.CTkLabel(edit_dialog, text="Phone:").pack(anchor=tk.W, padx=20, pady=(10, 0))
            phone_var = tk.StringVar(value=contact.phone or "")
            phone_entry = ctk.CTkEntry(edit_dialog, textvariable=phone_var, width=300)
            phone_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
            
            def update_contact():
                new_name = name_var.get().strip()
                telegram = telegram_var.get().strip()
                phone = phone_var.get().strip()
                
                if not new_name:
                    messagebox.showerror("Error", "Name is required", parent=edit_dialog)
                    return
                
                # Remove old contact
                profile.remove_contact(contact.name)
                
                # Create and add updated contact
                updated_contact = Contact(new_name, telegram, phone)
                profile.add_contact(updated_contact)
                
                # Update listbox
                contacts_listbox.delete(selected[0])
                contacts_listbox.insert(selected[0], new_name)
                
                edit_dialog.destroy()
            
            ctk.CTkButton(
                edit_dialog, 
                text="Update Contact", 
                command=update_contact,
                fg_color="#00BFFF",
                text_color="#FFFFFF",
                hover_color="#0080FF",
                width=200
            ).pack(pady=20)
        
        def remove_contact():
            selected = contacts_listbox.curselection()
            if selected:
                contact_name = contacts_listbox.get(selected[0])
                if profile.remove_contact(contact_name):
                    contacts_listbox.delete(selected[0])
        
        ctk.CTkButton(
            contacts_buttons_frame, 
            text="Add", 
            command=add_contact,
            fg_color="#00BFFF",
            text_color="#FFFFFF",
            hover_color="#0080FF",
            width=100
        ).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkButton(
            contacts_buttons_frame, 
            text="Edit", 
            command=edit_contact,
            fg_color="#FFC107",
            text_color="#000000",
            hover_color="#FFD54F",
            width=100
        ).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkButton(
            contacts_buttons_frame, 
            text="Remove", 
            command=remove_contact,
            fg_color="#F44336",
            text_color="#FFFFFF",
            hover_color="#D32F2F",
            width=100
        ).pack(side=tk.LEFT, padx=5)
        
        # Security settings
        security_frame = ctk.CTkFrame(tab_security, fg_color="#2A2A2A")
        security_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(security_frame, text="Security Settings", font=("Arial", 16, "bold")).pack(pady=10)
        
        # Password protection
        password_var = tk.BooleanVar(value=profile.authenticated)
        ctk.CTkCheckBox(
            security_frame, 
            text="Enable Password Protection", 
            variable=password_var,
            fg_color="#00BFFF",
            border_color="#AAAAAA"
        ).pack(anchor=tk.W, padx=20, pady=10)
        
        # Set password
        def set_password():
            password_dialog = ctk.CTkToplevel(settings_window)
            password_dialog.title("Set Password")
            password_dialog.geometry("400x200")
            password_dialog.configure(fg_color="#1E1E1E")
            
            ctk.CTkLabel(password_dialog, text="Set Password", font=("Arial", 16, "bold")).pack(pady=10)
            
            # Password
            ctk.CTkLabel(password_dialog, text="Password:").pack(anchor=tk.W, padx=20, pady=(10, 0))
            password_var = tk.StringVar()
            password_entry = ctk.CTkEntry(password_dialog, textvariable=password_var, width=300, show="*")
            password_entry.pack(anchor=tk.W, padx=20, pady=(0, 10))
            
            def save_password():
                password = password_var.get().strip()
                
                if not password:
                    messagebox.showerror("Error", "Password is required", parent=password_dialog)
                    return
                
                # Set password
                profile.authenticate(password)
                messagebox.showinfo("Success", "Password set successfully", parent=password_dialog)
                password_dialog.destroy()
            
            ctk.CTkButton(
                password_dialog, 
                text="Save Password", 
                command=save_password,
                fg_color="#00BFFF",
                text_color="#FFFFFF",
                hover_color="#0080FF",
                width=200
            ).pack(pady=20)
        
        ctk.CTkButton(
            security_frame, 
            text="Set Password", 
            command=set_password,
            fg_color="#00BFFF",
            text_color="#FFFFFF",
            hover_color="#0080FF",
            width=200
        ).pack(anchor=tk.W, padx=20, pady=10)
        
        # Export/Import encryption key
        key_frame = ctk.CTkFrame(security_frame, fg_color="#2A2A2A")
        key_frame.pack(fill=tk.X, padx=20, pady=10)
        
        def export_key():
            file_path = tk.filedialog.asksaveasfilename(
                defaultextension=".key",
                filetypes=[("Key files", "*.key"), ("All files", "*.*")],
                title="Export Encryption Key"
            )
            
            if file_path:
                if self.profile_manager.export_encryption_key(file_path):
                    messagebox.showinfo("Success", "Encryption key exported successfully", parent=settings_window)
                else:
                    messagebox.showerror("Error", "Failed to export encryption key", parent=settings_window)
        
        def import_key():
            file_path = tk.filedialog.askopenfilename(
                defaultextension=".key",
                filetypes=[("Key files", "*.key"), ("All files", "*.*")],
                title="Import Encryption Key"
            )
            
            if file_path:
                if self.profile_manager.import_encryption_key(file_path):
                    messagebox.showinfo("Success", "Encryption key imported successfully", parent=settings_window)
                else:
                    messagebox.showerror("Error", "Failed to import encryption key", parent=settings_window)
        
        ctk.CTkButton(
            key_frame, 
            text="Export Encryption Key", 
            command=export_key,
            fg_color="#333333",
            text_color="#FFFFFF",
            hover_color="#444444",
            width=200
        ).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkButton(
            key_frame, 
            text="Import Encryption Key", 
            command=import_key,
            fg_color="#333333",
            text_color="#FFFFFF",
            hover_color="#444444",
            width=200
        ).pack(side=tk.LEFT, padx=5)
        
        # Save button
        def save_settings():
            # Check if name changed
            new_name = name_var.get()
            old_name = profile.name
            
            profile.name = new_name
            profile.location = location_var.get()
            profile.preferences["voice_gender"] = voice_var.get()
            profile.preferences["voice_speed"] = speed_var.get()
            profile.preferences["favorite_apps"] = favorite_apps
            
            # Update voice settings
            voice_idx = 0 if voice_var.get() == "Male" else 1
            self.engine.setProperty('voice', self.voices[voice_idx].id)
            self.engine.setProperty('rate', speed_var.get())
            
            # Update Telegram settings
            api_id = api_id_var.get().strip()
            api_hash = api_hash_var.get().strip()
            session = session_var.get().strip()
            
            if api_id and api_hash and session:
                profile.set_telegram_session(session)
            
            # Update security settings
            if password_var.get() and not profile.is_authenticated():
                messagebox.showinfo("Info", "Please set a password to enable password protection", parent=settings_window)
            
            # Handle profile name change
            if new_name != old_name:
                # Create new profile with new name
                self.profile_manager.create_profile(new_name)
                new_profile = self.profile_manager.profiles[new_name]
                
                # Copy all data from old profile
                new_profile.location = profile.location
                new_profile.preferences = profile.preferences
                new_profile.command_history = profile.command_history
                new_profile.learning_data = profile.learning_data
                new_profile.contacts = profile.contacts
                new_profile.telegram_session = profile.telegram_session
                new_profile.authenticated = profile.authenticated
                new_profile.auth_token = profile.auth_token
                new_profile.auth_expiry = profile.auth_expiry
                
                # Save new profile and delete old one
                self.profile_manager.save_profile(new_profile)
                self.profile_manager.delete_profile(old_name)
                self.profile_manager.set_current_profile(new_name)
            else:
                # Just save the updated profile
                self.profile_manager.save_profile(profile)
            
            self.update_profile_display()
            settings_window.destroy()
            self.speak("Settings updated successfully")
        
        save_button = ctk.CTkButton(
            settings_window, 
            text="Save Settings", 
            command=save_settings,
            fg_color="#00BFFF",
            text_color="#FFFFFF",
            hover_color="#0080FF",
            height=40,
            corner_radius=20,
            width=200
        )
        save_button.pack(pady=20)
    
    # Command handlers
    def handle_message(self, text):
        profile = self.profile_manager.get_current_profile()
        
        # Check if Telegram is configured
        if not self.telegram.connected:
            if profile and profile.telegram_session:
                # Try to initialize with saved session
                if not self.telegram.api_id or not self.telegram.api_hash:
                    return "Please configure your Telegram API credentials in settings."
                
                success = self.telegram.initialize(profile.telegram_session)
                if not success:
                    return f"Failed to connect to Telegram: {self.telegram.error_message}. Please check your settings."
            else:
                return "Telegram is not configured. Please set up your Telegram account in settings."
        
        # Extract recipient and message content
        recipient = None
        message_content = None
        
        if "message" in text and "to" in text and "saying" in text:
            # Format: "message to [recipient] saying [content]"
            parts = text.split("to")
            if len(parts) > 1:
                recipient_parts = parts[1].split("saying")
                if len(recipient_parts) > 1:
                    recipient = recipient_parts[0].strip()
                    message_content = recipient_parts[1].strip()
        elif "message" in text and "to" in text:
            # Format: "message to [recipient]"
            parts = text.split("to")
            if len(parts) > 1:
                recipient = parts[1].strip()
                message_content = None  # Will prompt for message content
        
        # Check if we have a contact with this name
        if recipient and profile:
            contact = profile.get_contact(recipient)
            if contact and contact.telegram_username:
                recipient = contact.telegram_username if not contact.telegram_username.startswith('@') else contact.telegram_username
        
        if recipient and message_content:
            # Send the message
            success, response = self.telegram.send_message(recipient, message_content)
            
            if success:
                # Update contact's last contacted time if it's a known contact
                if profile:
                    contact = profile.get_contact(recipient)
                    if contact:
                        contact.update_contact_time()
                
                return response
            else:
                return response
        elif recipient:
            return f"What message would you like to send to {recipient}?"
        else:
            return "Who would you like to message?"
    
    def handle_call(self, text):
        # Extract recipient
        if "call" in text:
            words = text.split()
            call_index = words.index("call")
            if call_index + 1 < len(words):
                recipient = words[call_index + 1]
                return f"Calling {recipient}... Note: Actual calling functionality is not implemented in this demo."
        return "Who would you like to call?"
    
    def handle_alarm(self, text):
        # Extract time
        if "alarm" in text and "for" in text:
            parts = text.split("for")
            if len(parts) > 1:
                time_str = parts[1].strip()
                return f"Alarm set for {time_str}."
        return "When would you like to set the alarm for?"
    
    def handle_reminder(self, text):
        # Extract reminder details
        if "remind" in text and "to" in text:
            parts = text.split("to")
            if len(parts) > 1:
                task = parts[1].strip()
                return f"I'll remind you to {task}. When would you like to be reminded?"
        return "What would you like me to remind you about?"
    
    def handle_timer(self, text):
        # Extract duration
        if "timer" in text and "for" in text:
            parts = text.split("for")
            if len(parts) > 1:
                duration = parts[1].strip()
                return f"Timer set for {duration}."
        return "How long would you like to set the timer for?"
    
    def handle_todo(self, text):
        # Handle to-do list operations
        if "add" in text and "to" in text and "list" in text:
            parts = text.split("add")[1].split("to")[0].strip()
            return f"Added '{parts}' to your to-do list."
        elif "show" in text and "list" in text:
            return "Here's your to-do list: 1. Example task"
        return "What would you like to do with your to-do list?"
    
    def handle_weather(self, text):
        # Extract location
        location = "your current location"
        if "weather" in text and "in" in text:
            parts = text.split("in")
            if len(parts) > 1:
                location = parts[1].strip()
        
        # Use profile location if available and no specific location mentioned
        if location == "your current location":
            profile = self.profile_manager.get_current_profile()
            if profile and profile.location:
                location = profile.location
        
        # Simulate weather data
        conditions = ["sunny", "partly cloudy", "cloudy", "rainy", "stormy"]
        temps = range(60, 85)
        
        condition = random.choice(conditions)
        temp = random.choice(temps)
        
        return f"The weather in {location} is currently {condition} with a temperature of {temp}°F."
    
    def handle_news(self, text):
        # Extract topic
        topic = "general"
        if "news" in text and "about" in text:
            parts = text.split("about")
            if len(parts) > 1:
                topic = parts[1].strip()
        
        return f"Here are the latest headlines about {topic}: [News headlines would appear here]"
    
    def handle_music(self, text):
        # Extract artist/song
        if "play" in text:
            parts = text.split("play")
            if len(parts) > 1:
                song = parts[1].strip()
                return f"Playing {song}..."
        return "What music would you like me to play?"
    
    def handle_open_app(self, text):
        # Extract app name
        app_name = None
        
        # Check for specific app names first
        for app in ["spotify", "chrome", "firefox", "telegram", "notepad", "calculator"]:
            if app in text.lower():
                app_name = app
                break
        
        # If no specific app found, look for "open" + app name pattern
        if not app_name:
            if "open" in text:
                parts = text.split("open")
                if len(parts) > 1:
                    app_name = parts[1].strip()
            elif "launch" in text:
                parts = text.split("launch")
                if len(parts) > 1:
                    app_name = parts[1].strip()
            elif "start" in text:
                parts = text.split("start")
                if len(parts) > 1:
                    app_name = parts[1].strip()
            elif "run" in text:
                parts = text.split("run")
                if len(parts) > 1:
                    app_name = parts[1].strip()
        
        if app_name:
            success, message = self.app_launcher.launch_app(app_name)
            
            # Add to favorite apps if successful
            if success:
                profile = self.profile_manager.get_current_profile()
                if profile:
                    profile.add_favorite_app(app_name)
                    self.profile_manager.save_profile(profile)
            
            return message
        
        return "Which application would you like to open?"
    
    def handle_spotify(self, text):
        # Launch Spotify
        success, message = self.app_launcher.launch_app("spotify")
        
        # If just launching Spotify
        if "open" in text or "launch" in text or "start" in text or "run" in text:
            return message
        
        # If playing specific music
        if "play" in text:
            parts = text.split("play")
            if len(parts) > 1:
                song = parts[1].strip()
                return f"Opening Spotify and playing {song}..."
        
        return message
    
    def handle_chrome(self, text):
        # Launch Chrome
        success, message = self.app_launcher.launch_app("chrome")
        
        # If just launching Chrome
        if "open" in text or "launch" in text or "start" in text or "run" in text:
            if not ("go to" in text or "visit" in text or "open" in text and ".com" in text):
                return message
        
        # If visiting a website
        website = None
        if "go to" in text:
            parts = text.split("go to")
            if len(parts) > 1:
                website = parts[1].strip()
        elif "visit" in text:
            parts = text.split("visit")
            if len(parts) > 1:
                website = parts[1].strip()
        elif "open" in text and ".com" in text:
            parts = text.split("open")
            if len(parts) > 1:
                for word in parts[1].split():
                    if ".com" in word or ".org" in word or ".net" in word:
                        website = word
                        break
        
        if website:
            success, web_message = self.app_launcher.open_website(website, "chrome")
            return web_message
        
        return message
    
    def handle_firefox(self, text):
        # Launch Firefox
        success, message = self.app_launcher.launch_app("firefox")
        
        # If just launching Firefox
        if "open" in text or "launch" in text or "start" in text or "run" in text:
            if not ("go to" in text or "visit" in text or "open" in text and ".com" in text):
                return message
        
        # If visiting a website
        website = None
        if "go to" in text:
            parts = text.split("go to")
            if len(parts) > 1:
                website = parts[1].strip()
        elif "visit" in text:
            parts = text.split("visit")
            if len(parts) > 1:
                website = parts[1].strip()
        elif "open" in text and ".com" in text:
            parts = text.split("open")
            if len(parts) > 1:
                for word in parts[1].split():
                    if ".com" in word or ".org" in word or ".net" in word:
                        website = word
                        break
        
        if website:
            success, web_message = self.app_launcher.open_website(website, "firefox")
            return web_message
        
        return message
    
    def handle_telegram(self, text):
        # Launch Telegram
        success, message = self.app_launcher.launch_app("telegram")
        
        # If just launching Telegram
        if "open" in text or "launch" in text or "start" in text or "run" in text:
            return message
        
        # If sending a message, delegate to handle_message
        if "message" in text or "send" in text:
            return self.handle_message(text)
        
        return message
    
    def handle_search(self, text):
        # Extract search query and browser preference
        query = None
        browser = None
        
        # Check for browser preference
        if "chrome" in text:
            browser = "chrome"
        elif "firefox" in text:
            browser = "firefox"
        
        # Extract query
        if "search for" in text:
            parts = text.split("search for")
            if len(parts) > 1:
                query = parts[1].strip()
        elif "search" in text:
            parts = text.split("search")
            if len(parts) > 1:
                query = parts[1].strip()
        elif "google" in text:
            parts = text.split("google")
            if len(parts) > 1:
                query = parts[1].strip()
        elif "find" in text:
            parts = text.split("find")
            if len(parts) > 1:
                query = parts[1].strip()
        elif "look up" in text:
            parts = text.split("look up")
            if len(parts) > 1:
                query = parts[1].strip()
        
        if query:
            success, message = self.app_launcher.search_web(query, browser)
            return f"Searching for '{query}'"
        
        return "What would you like to search for?"
    
    def handle_contact(self, text):
        profile = self.profile_manager.get_current_profile()
        
        if not profile:
            return "Please create a profile first to manage contacts."
        
        # Add contact
        if "add" in text and "contact" in text:
            # Extract contact name
            name = None
            if "named" in text:
                parts = text.split("named")
                if len(parts) > 1:
                    name = parts[1].strip()
            
            if name:
                # Check if contact already exists
                if profile.get_contact(name):
                    return f"A contact named {name} already exists. Would you like to update it?"
                
                # Create new contact
                contact = Contact(name)
                profile.add_contact(contact)
                self.profile_manager.save_profile(profile)
                
                return f"Contact {name} added. Would you like to add their Telegram username or phone number?"
            else:
                return "What is the name of the contact you'd like to add?"
        
        # List contacts
        elif "list" in text and "contacts" in text or "show" in text and "contacts" in text:
            contacts = profile.get_all_contacts()
            
            if not contacts:
                return "You don't have any contacts yet. Would you like to add one?"
            
            contact_list = "\n".join([f"- {contact.name}" for contact in contacts])
            return f"Here are your contacts:\n{contact_list}"
        
        # Remove contact
        elif "remove" in text and "contact" in text or "delete" in text and "contact" in text:
            # Extract contact name
            name = None
            parts = text.split("contact")
            if len(parts) > 1:
                name = parts[1].strip()
            
            if name:
                if profile.remove_contact(name):
                    self.profile_manager.save_profile(profile)
                    return f"Contact {name} has been removed."
                else:
                    return f"I couldn't find a contact named {name}."
            else:
                return "Which contact would you like to remove?"
        
        # Find contact
        elif "find" in text and "contact" in text:
            # Extract contact name
            name = None
            parts = text.split("contact")
            if len(parts) > 1:
                name = parts[1].strip()
            
            if name:
                contact = profile.get_contact(name)
                if contact:
                    details = []
                    if contact.telegram_username:
                        details.append(f"Telegram: {contact.telegram_username}")
                    if contact.phone:
                        details.append(f"Phone: {contact.phone}")
                    if contact.email:
                        details.append(f"Email: {contact.email}")
                    
                    if details:
                        return f"Contact details for {contact.name}:\n" + "\n".join(details)
                    else:
                        return f"I found {contact.name} in your contacts, but there are no details saved."
                else:
                    return f"I couldn't find a contact named {name}."
            else:
                return "Which contact are you looking for?"
        
        return "What would you like to do with your contacts? You can add, list, find, or remove contacts."
    
    def handle_profile(self, text):
        # Handle profile-related commands
        if "create" in text and "profile" in text:
            return "Let's create a new profile. What name would you like to use?"
        
        elif "switch" in text and "profile" in text:
            profile_names = self.profile_manager.get_profile_names()
            if not profile_names:
                return "You don't have any profiles yet. Let's create one."
            
            profiles_str = ", ".join(profile_names)
            return f"Available profiles: {profiles_str}. Which one would you like to switch to?"
        
        elif "delete" in text and "profile" in text:
            current_profile = self.profile_manager.get_current_profile()
            if current_profile:
                return f"Are you sure you want to delete the profile '{current_profile.name}'? Say 'yes, delete profile' to confirm."
            return "No active profile to delete."
        
        elif "yes, delete profile" in text:
            current_profile = self.profile_manager.get_current_profile()
            if current_profile:
                name = current_profile.name
                if self.profile_manager.delete_profile(name):
                    # Switch to another profile or create default
                    profile_names = self.profile_manager.get_profile_names()
                    if profile_names:
                        self.profile_manager.set_current_profile(profile_names[0])
                    else:
                        self.profile_manager.create_profile("Default")
                        self.profile_manager.set_current_profile("Default")
                    
                    self.update_profile_display()
                    return f"Profile '{name}' has been deleted."
            return "Failed to delete profile."
        
        return "What would you like to do with your profile? You can create, switch, or delete profiles."
    
    def handle_feedback(self, text):
        self.show_feedback_dialog()
        return "Thank you for providing feedback!"
    
    def handle_authenticate(self, text):
        profile = self.profile_manager.get_current_profile()
        if not profile:
            return "Please create a profile first."
        
        if profile.is_authenticated():
            return "You are already authenticated."
        
        # Ask for password
        password = simpledialog.askstring("Authentication", "Please enter your password:", show="*", parent=self.root)
        
        if password:
            token = profile.authenticate(password)
            if profile.is_authenticated():
                self.update_auth_status(True)
                self.profile_manager.save_profile(profile)
                return "Authentication successful."
            else:
                return "Authentication failed. Incorrect password."
        else:
            return "Authentication cancelled."
    
    def handle_logout(self, text):
        profile = self.profile_manager.get_current_profile()
        if not profile:
            return "No active profile."
        
        if not profile.is_authenticated():
            return "You are not currently authenticated."
        
        profile.logout()
        self.update_auth_status(False)
        self.profile_manager.save_profile(profile)
        return "You have been logged out."
    
    def handle_help(self, text):
        return """I can help you with:
1. Sending messages via Telegram
2. Opening applications like Spotify, Chrome, Firefox, and Telegram
3. Searching the web using Chrome or Firefox
4. Setting alarms and reminders
5. Creating to-do lists
6. Checking weather and news
7. Managing your contacts
8. Managing your profile and security settings

Just ask me what you need!"""
    
    def handle_exit(self, text):
        # Save current profile before exiting
        profile = self.profile_manager.get_current_profile()
        if profile:
            self.profile_manager.save_profile(profile)
        
        # Disconnect Telegram if connected
        if self.telegram.connected:
            self.telegram.disconnect()
        
        self.root.after(1000, self.root.destroy)
        return "Goodbye! Have a great day."
    
    def general_conversation(self, text):
        # Simple conversation handling
        greetings = ["hi", "hello", "hey", "greetings"]
        for greeting in greetings:
            if greeting in text:
                profile = self.profile_manager.get_current_profile()
                if profile and profile.name:
                    return f"Hello, {profile.name}! How may I assist you today?"
                return f"Hello! How may I assist you today?"
        
        if "how are you" in text:
            return "I'm functioning at optimal parameters, thank you for asking. How may I assist you?"
        
        if "thank" in text:
            return "You're welcome! Is there anything else you need help with?"
        
        if "your name" in text:
            return "I am J.A.R.V.I.S., Just A Rather Very Intelligent System. How may I assist you today?"
        
        if "what can you do" in text:
            return self.handle_help(text)
        
        # If no specific pattern is matched, provide a general response
        return "I'm not sure I understand. Can you rephrase that or ask me something specific?"

class JarvisTests(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test profiles
        self.test_dir = "test_profiles"
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
        
        # Initialize components for testing
        self.profile_manager = ProfileManager(self.test_dir)
        self.app_launcher = AppLauncher()
        self.learning_system = LearningSystem()
    
    def tearDown(self):
        # Clean up test directory
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_profile_creation(self):
        # Test creating a profile
        self.profile_manager.create_profile("TestUser", "TestLocation")
        self.assertIn("TestUser", self.profile_manager.get_profile_names())
        
        # Test setting current profile
        self.assertTrue(self.profile_manager.set_current_profile("TestUser"))
        profile = self.profile_manager.get_current_profile()
        self.assertEqual(profile.name, "TestUser")
        self.assertEqual(profile.location, "TestLocation")
    
    def test_contact_management(self):
        # Create a profile
        self.profile_manager.create_profile("TestUser")
        self.profile_manager.set_current_profile("TestUser")
        profile = self.profile_manager.get_current_profile()
        
        # Add a contact
        contact = Contact("TestContact", "@test_user", "123456789")
        profile.add_contact(contact)
        
        # Test retrieving contact
        retrieved_contact = profile.get_contact("TestContact")
        self.assertIsNotNone(retrieved_contact)
        self.assertEqual(retrieved_contact.telegram_username, "@test_user")
        
        # Test removing contact
        self.assertTrue(profile.remove_contact("TestContact"))
        self.assertIsNone(profile.get_contact("TestContact"))
    
    def test_app_launcher(self):
        # Test app path retrieval
        paths = self.app_launcher._get_default_app_paths()
        self.assertIn("chrome", paths)
        self.assertIn("telegram", paths)
    
    def test_learning_system(self):
        # Test learning from commands
        self.learning_system.learn_from_command("open chrome", "open", True)
        self.learning_system.learn_from_command("search for python tutorials", "search", True)
        
        # Test prediction
        prediction = self.learning_system.predict_command_type("open firefox")
        self.assertEqual(prediction, "open")
        
        # Test suggestions
        suggestions = self.learning_system.get_command_suggestions("sea")
        self.assertIn("search", suggestions)

def run_tests():
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

def main():
    # Create necessary directories
    if not os.path.exists("profiles"):
        os.makedirs("profiles")
    
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    # Set up customtkinter
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Create and run the application
    root = tk.Tk()
    app = JarvisAssistant(root)
    root.mainloop()

if __name__ == "__main__":
    main()