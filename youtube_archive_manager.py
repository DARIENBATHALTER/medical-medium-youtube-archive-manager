#!/usr/bin/env python3
"""
Medical Medium YouTube Archive Manager
Automated system for downloading and processing YouTube videos with GUI
Features: GUI interface, automatic scheduling, system startup integration
"""

import os
import sys
import json
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import schedule
import time

# Third-party imports (will be installed via requirements)
try:
    import yt_dlp
    import openai
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"Missing required packages. Please install: pip install -r requirements.txt")
    print(f"Error: {e}")
    sys.exit(1)

class YouTubeArchiveManager:
    """Main application class for YouTube Archive Management"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Medical Medium YouTube Archive Manager")
        self.root.geometry("1000x800")
        self.root.minsize(800, 600)
        
        # Configuration
        self.config = {
            "archive_path": "/mnt/MM/MedicalMediumArchive/YouTube/MM_YT_archive",
            "channel_id": "UCUORv_qpgmg8N5plVqlYjXg",  # Medical Medium channel
            "youtube_api_key": "",
            "openai_api_key": "",
            "auto_start": True,
            "check_time": "00:00",
            "last_check": None,
            "download_quality": "best",
            "max_concurrent": 3
        }
        
        # Load configuration
        self.config_file = Path.home() / ".youtube_archive_config.json"
        self.load_config()
        
        # Initialize logging
        self.setup_logging()
        
        # Initialize APIs
        self.youtube = None
        self.openai_client = None
        
        # GUI state
        self.is_running = False
        self.scheduler_thread = None
        
        # Setup GUI
        self.create_gui()
        
        # Initialize scheduler if auto-start enabled
        if self.config["auto_start"]:
            self.start_scheduler()

    def setup_logging(self):
        """Setup logging configuration"""
        log_file = Path(self.config["archive_path"]) / "logs" / "archive_manager.log"
        log_file.parent.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")

    def create_gui(self):
        """Create the main GUI interface"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Main tab
        self.create_main_tab(notebook)
        
        # Configuration tab
        self.create_config_tab(notebook)
        
        # Logs tab
        self.create_logs_tab(notebook)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_main_tab(self, notebook):
        """Create main control tab"""
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="Main Control")
        
        # Archive status section
        status_frame = ttk.LabelFrame(main_frame, text="Archive Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Status labels
        self.archive_stats = {
            "total_videos": tk.StringVar(value="Loading..."),
            "total_comments": tk.StringVar(value="Loading..."),
            "last_update": tk.StringVar(value="Loading..."),
            "next_check": tk.StringVar(value="Not scheduled")
        }
        
        row = 0
        for key, var in self.archive_stats.items():
            ttk.Label(status_frame, text=f"{key.replace('_', ' ').title()}:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(status_frame, textvariable=var).grid(row=row, column=1, sticky=tk.W, padx=20, pady=2)
            row += 1
        
        # Control buttons section
        control_frame = ttk.LabelFrame(main_frame, text="Manual Controls")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Check for New Videos", 
                  command=self.manual_check, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Start Auto Scheduler", 
                  command=self.start_scheduler, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Stop Auto Scheduler", 
                  command=self.stop_scheduler, width=20).pack(side=tk.LEFT, padx=5)
        
        # Additional manual controls
        button_frame2 = ttk.Frame(control_frame)
        button_frame2.pack(pady=5)
        
        ttk.Button(button_frame2, text="Update Metadata", 
                  command=self.update_metadata, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame2, text="Process Missing Transcripts", 
                  command=self.process_missing_transcripts, width=20).pack(side=tk.LEFT, padx=5)
        
        # Progress section
        progress_frame = ttk.LabelFrame(main_frame, text="Current Progress")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.progress_var = tk.StringVar(value="Idle")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(pady=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        # Recent activity log
        self.activity_text = scrolledtext.ScrolledText(progress_frame, height=15, state=tk.DISABLED)
        self.activity_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Load initial stats
        self.update_stats()

    def create_config_tab(self, notebook):
        """Create configuration tab"""
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="Configuration")
        
        # API Keys section
        api_frame = ttk.LabelFrame(config_frame, text="API Configuration")
        api_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # YouTube API Key
        ttk.Label(api_frame, text="YouTube Data API Key:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.youtube_key_var = tk.StringVar(value=self.config.get("youtube_api_key", ""))
        youtube_entry = ttk.Entry(api_frame, textvariable=self.youtube_key_var, show="*", width=50)
        youtube_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # OpenAI API Key
        ttk.Label(api_frame, text="OpenAI API Key:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.openai_key_var = tk.StringVar(value=self.config.get("openai_api_key", ""))
        openai_entry = ttk.Entry(api_frame, textvariable=self.openai_key_var, show="*", width=50)
        openai_entry.grid(row=1, column=1, padx=5, pady=5)
        
        # Archive settings section
        archive_frame = ttk.LabelFrame(config_frame, text="Archive Settings")
        archive_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Archive path
        ttk.Label(archive_frame, text="Archive Path:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.archive_path_var = tk.StringVar(value=self.config.get("archive_path", ""))
        ttk.Entry(archive_frame, textvariable=self.archive_path_var, width=60).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(archive_frame, text="Browse", 
                  command=self.browse_archive_path).grid(row=0, column=2, padx=5, pady=5)
        
        # Channel ID
        ttk.Label(archive_frame, text="Channel ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.channel_id_var = tk.StringVar(value=self.config.get("channel_id", ""))
        ttk.Entry(archive_frame, textvariable=self.channel_id_var, width=40).grid(row=1, column=1, padx=5, pady=5)
        
        # Scheduler settings section
        scheduler_frame = ttk.LabelFrame(config_frame, text="Scheduler Settings")
        scheduler_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Auto start
        self.auto_start_var = tk.BooleanVar(value=self.config.get("auto_start", True))
        ttk.Checkbutton(scheduler_frame, text="Start scheduler automatically", 
                       variable=self.auto_start_var).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Check time
        ttk.Label(scheduler_frame, text="Daily Check Time (HH:MM):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.check_time_var = tk.StringVar(value=self.config.get("check_time", "00:00"))
        ttk.Entry(scheduler_frame, textvariable=self.check_time_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Download settings section
        download_frame = ttk.LabelFrame(config_frame, text="Download Settings")
        download_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Quality
        ttk.Label(download_frame, text="Video Quality:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.quality_var = tk.StringVar(value=self.config.get("download_quality", "best"))
        quality_combo = ttk.Combobox(download_frame, textvariable=self.quality_var, 
                                    values=["best", "worst", "720p", "1080p"])
        quality_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Max concurrent
        ttk.Label(download_frame, text="Max Concurrent Downloads:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_concurrent_var = tk.StringVar(value=str(self.config.get("max_concurrent", 3)))
        ttk.Spinbox(download_frame, from_=1, to=10, textvariable=self.max_concurrent_var, 
                   width=5).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Save button
        ttk.Button(config_frame, text="Save Configuration", 
                  command=self.save_configuration).pack(pady=10)

    def create_logs_tab(self, notebook):
        """Create logs viewing tab"""
        logs_frame = ttk.Frame(notebook)
        notebook.add(logs_frame, text="Logs")
        
        # Log text area
        self.logs_text = scrolledtext.ScrolledText(logs_frame, state=tk.DISABLED)
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Control buttons
        button_frame = ttk.Frame(logs_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="Refresh Logs", 
                  command=self.refresh_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Logs", 
                  command=self.clear_logs).pack(side=tk.LEFT, padx=5)
        
        # Load initial logs
        self.refresh_logs()

    def browse_archive_path(self):
        """Browse for archive directory"""
        path = filedialog.askdirectory(initialdir=self.archive_path_var.get())
        if path:
            self.archive_path_var.set(path)

    def save_configuration(self):
        """Save current configuration"""
        self.config["youtube_api_key"] = self.youtube_key_var.get()
        self.config["openai_api_key"] = self.openai_key_var.get()
        self.config["archive_path"] = self.archive_path_var.get()
        self.config["channel_id"] = self.channel_id_var.get()
        self.config["auto_start"] = self.auto_start_var.get()
        self.config["check_time"] = self.check_time_var.get()
        self.config["download_quality"] = self.quality_var.get()
        self.config["max_concurrent"] = int(self.max_concurrent_var.get())
        
        self.save_config()
        
        # Reinitialize APIs with new keys
        self.initialize_apis()
        
        messagebox.showinfo("Configuration", "Configuration saved successfully!")

    def initialize_apis(self):
        """Initialize YouTube and OpenAI APIs"""
        try:
            if self.config["youtube_api_key"]:
                self.youtube = build('youtube', 'v3', developerKey=self.config["youtube_api_key"])
                self.log_activity("YouTube API initialized successfully")
            
            if self.config["openai_api_key"]:
                openai.api_key = self.config["openai_api_key"]
                self.openai_client = openai
                self.log_activity("OpenAI API initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing APIs: {e}")
            self.log_activity(f"Error initializing APIs: {e}")

    def update_stats(self):
        """Update archive statistics"""
        try:
            archive_path = Path(self.config["archive_path"])
            
            if not archive_path.exists():
                for key in self.archive_stats:
                    self.archive_stats[key].set("Archive path not found")
                return
            
            # Load video stats
            videos_file = archive_path / "videos.json"
            comments_file = archive_path / "comments.json"
            
            if videos_file.exists():
                with open(videos_file, 'r') as f:
                    videos = json.load(f)
                    self.archive_stats["total_videos"].set(str(len(videos)))
                    
                    # Get last update time
                    if videos:
                        latest = max(videos, key=lambda x: x.get('scraped_at', ''))
                        self.archive_stats["last_update"].set(latest.get('scraped_at', 'Unknown'))
            else:
                self.archive_stats["total_videos"].set("0")
                self.archive_stats["last_update"].set("Never")
            
            if comments_file.exists():
                with open(comments_file, 'r') as f:
                    comments = json.load(f)
                    self.archive_stats["total_comments"].set(str(len(comments)))
            else:
                self.archive_stats["total_comments"].set("0")
                
        except Exception as e:
            self.logger.error(f"Error updating stats: {e}")

    def log_activity(self, message):
        """Log activity to the GUI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        
        self.activity_text.config(state=tk.NORMAL)
        self.activity_text.insert(tk.END, full_message)
        self.activity_text.see(tk.END)
        self.activity_text.config(state=tk.DISABLED)
        
        # Also log to file
        self.logger.info(message)

    def manual_check(self):
        """Manually trigger new video check"""
        if not self.youtube:
            messagebox.showerror("Error", "YouTube API not configured!")
            return
            
        thread = threading.Thread(target=self.check_new_videos)
        thread.daemon = True
        thread.start()

    def start_scheduler(self):
        """Start the automatic scheduler"""
        if self.is_running:
            return
            
        self.is_running = True
        
        # Schedule daily check
        schedule.clear()
        schedule.every().day.at(self.config["check_time"]).do(self.check_new_videos)
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self.run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        self.log_activity(f"Scheduler started - daily check at {self.config['check_time']}")
        self.update_next_check_time()

    def stop_scheduler(self):
        """Stop the automatic scheduler"""
        self.is_running = False
        schedule.clear()
        self.archive_stats["next_check"].set("Not scheduled")
        self.log_activity("Scheduler stopped")

    def run_scheduler(self):
        """Run the scheduler loop"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def update_next_check_time(self):
        """Update next check time display"""
        if schedule.jobs:
            next_run = schedule.next_run()
            self.archive_stats["next_check"].set(next_run.strftime("%Y-%m-%d %H:%M"))

    def check_new_videos(self):
        """Check for and process new videos"""
        if not self.youtube:
            self.log_activity("Error: YouTube API not configured")
            return
            
        try:
            self.log_activity("Starting new video check...")
            self.progress_bar.start()
            self.progress_var.set("Checking for new videos...")
            
            # Import and initialize archive manager
            from archive_manager import ArchiveManager
            archive_manager = ArchiveManager(self.config)
            
            # Check for new videos
            results = archive_manager.check_for_new_videos()
            
            # Log results
            self.log_activity(f"New video check complete:")
            self.log_activity(f"  - New videos found: {results.get('new_videos', 0)}")
            self.log_activity(f"  - Successfully processed: {results.get('processed', 0)}")
            self.log_activity(f"  - Errors: {results.get('errors', 0)}")
            
            # Update stats
            self.update_stats()
            
            if results.get('new_videos', 0) > 0:
                messagebox.showinfo("New Videos", 
                    f"Found and processed {results.get('processed', 0)} new videos!\n"
                    f"Errors: {results.get('errors', 0)}")
            else:
                self.log_activity("No new videos found")
            
        except Exception as e:
            self.logger.error(f"Error checking new videos: {e}")
            self.log_activity(f"Error checking new videos: {e}")
            messagebox.showerror("Error", f"Failed to check for new videos: {e}")
            
        finally:
            self.progress_bar.stop()
            self.progress_var.set("Idle")

    def update_metadata(self):
        """Update metadata for existing videos"""
        if not self.youtube:
            self.log_activity("Error: YouTube API not configured")
            return
            
        try:
            self.log_activity("Starting metadata update...")
            self.progress_bar.start()
            self.progress_var.set("Updating metadata...")
            
            from archive_manager import ArchiveManager
            archive_manager = ArchiveManager(self.config)
            
            results = archive_manager.update_existing_metadata()
            
            self.log_activity(f"Metadata update complete:")
            self.log_activity(f"  - Videos updated: {results.get('updated', 0)}")
            self.log_activity(f"  - Errors: {results.get('errors', 0)}")
            
            self.update_stats()
            
            messagebox.showinfo("Metadata Update", 
                f"Updated metadata for {results.get('updated', 0)} videos")
            
        except Exception as e:
            self.logger.error(f"Error updating metadata: {e}")
            self.log_activity(f"Error updating metadata: {e}")
            messagebox.showerror("Error", f"Failed to update metadata: {e}")
            
        finally:
            self.progress_bar.stop()
            self.progress_var.set("Idle")

    def process_missing_transcripts(self):
        """Process videos with missing transcripts/summaries"""
        if not self.openai_client:
            self.log_activity("Error: OpenAI API not configured")
            return
            
        try:
            self.log_activity("Processing missing transcripts...")
            self.progress_bar.start()
            self.progress_var.set("Processing transcripts...")
            
            from archive_manager import ArchiveManager
            archive_manager = ArchiveManager(self.config)
            
            results = archive_manager.process_missing_transcripts()
            
            self.log_activity(f"Transcript processing complete:")
            self.log_activity(f"  - Videos processed: {results.get('processed', 0)}")
            self.log_activity(f"  - Errors: {results.get('errors', 0)}")
            
            self.update_stats()
            
            messagebox.showinfo("Transcript Processing", 
                f"Processed {results.get('processed', 0)} videos with missing transcripts")
            
        except Exception as e:
            self.logger.error(f"Error processing transcripts: {e}")
            self.log_activity(f"Error processing transcripts: {e}")
            messagebox.showerror("Error", f"Failed to process transcripts: {e}")
            
        finally:
            self.progress_bar.stop()
            self.progress_var.set("Idle")

    def refresh_logs(self):
        """Refresh log display"""
        try:
            log_file = Path(self.config["archive_path"]) / "logs" / "archive_manager.log"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    content = f.read()
                    
                self.logs_text.config(state=tk.NORMAL)
                self.logs_text.delete(1.0, tk.END)
                self.logs_text.insert(tk.END, content)
                self.logs_text.see(tk.END)
                self.logs_text.config(state=tk.DISABLED)
        except Exception as e:
            self.logger.error(f"Error refreshing logs: {e}")

    def clear_logs(self):
        """Clear log display"""
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.delete(1.0, tk.END)
        self.logs_text.config(state=tk.DISABLED)

    def on_closing(self):
        """Handle application closing"""
        self.stop_scheduler()
        self.save_config()
        self.root.destroy()

    def run(self):
        """Run the application"""
        self.initialize_apis()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Medical Medium YouTube Archive Manager")
    parser.add_argument("--headless", action="store_true", 
                       help="Run in headless mode (no GUI)")
    parser.add_argument("--check-only", action="store_true",
                       help="Check for new videos once and exit")
    parser.add_argument("--config", type=str, 
                       help="Path to configuration file")
    
    args = parser.parse_args()
    
    if args.check_only:
        # Run check-only mode
        from archive_manager import ArchiveManager
        import json
        from pathlib import Path
        
        # Load configuration
        config_file = Path(args.config) if args.config else Path.home() / ".youtube_archive_config.json"
        config = {
            "archive_path": "/mnt/MM/MedicalMediumArchive/YouTube/MM_YT_archive",
            "channel_id": "UCUORv_qpgmg8N5plVqlYjXg",
            "youtube_api_key": "",
            "openai_api_key": "",
            "download_quality": "best",
            "max_concurrent": 3
        }
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                config.update(json.load(f))
        
        # Run check
        try:
            archive_manager = ArchiveManager(config)
            results = archive_manager.check_for_new_videos()
            print(f"Check complete: {results}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
            
    elif args.headless:
        # Run headless mode with scheduler only
        print("Starting YouTube Archive Manager in headless mode...")
        # This would implement a headless version with just the scheduler
        # For now, we'll just use the GUI version
        app = YouTubeArchiveManager()
        app.root.withdraw()  # Hide the main window
        app.start_scheduler()
        
        try:
            app.root.mainloop()
        except KeyboardInterrupt:
            print("\nShutting down...")
            app.stop_scheduler()
    else:
        # Normal GUI mode
        app = YouTubeArchiveManager()
        app.run()