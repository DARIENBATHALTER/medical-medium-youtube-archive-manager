"""
Archive Manager Module
Handles integration with existing archive structure and data management
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from youtube_processor import YouTubeProcessor
from openai_processor import OpenAIProcessor

class ArchiveManager:
    """Manages the YouTube archive and coordinates all processing"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.archive_path = Path(config["archive_path"])
        self.logger = logging.getLogger(__name__)
        
        # Initialize processors
        self.youtube_processor = YouTubeProcessor(config)
        self.openai_processor = OpenAIProcessor(config)
        
        # Archive file paths
        self.videos_file = self.archive_path / "videos.json"
        self.comments_file = self.archive_path / "comments.json"
        self.keywords_file = self.archive_path / "keywords.json"
        self.transcript_index_file = self.archive_path / "transcript_index.json"
        self.video_mapping_file = self.archive_path / "video-mapping.json"
        self.videos_dir = self.archive_path / "videos"
        
        # Ensure directories exist
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        (self.archive_path / "logs").mkdir(parents=True, exist_ok=True)
        
        # Status tracking
        self.processing_lock = threading.Lock()
        self.current_status = "idle"
    
    def load_existing_data(self) -> Dict:
        """
        Load existing archive data
        
        Returns:
            Dictionary containing existing videos, comments, keywords, etc.
        """
        data = {
            "videos": [],
            "comments": [],
            "keywords": {},
            "transcript_index": {"metadata": {}, "transcripts": {}, "word_index": {}},
            "video_mapping": {}
        }
        
        try:
            # Load videos
            if self.videos_file.exists():
                with open(self.videos_file, 'r', encoding='utf-8') as f:
                    data["videos"] = json.load(f)
                self.logger.info(f"Loaded {len(data['videos'])} existing videos")
            
            # Load comments
            if self.comments_file.exists():
                with open(self.comments_file, 'r', encoding='utf-8') as f:
                    data["comments"] = json.load(f)
                self.logger.info(f"Loaded {len(data['comments'])} existing comments")
            
            # Load keywords
            if self.keywords_file.exists():
                with open(self.keywords_file, 'r', encoding='utf-8') as f:
                    data["keywords"] = json.load(f)
                self.logger.info(f"Loaded {len(data['keywords'])} keyword entries")
            
            # Load transcript index
            if self.transcript_index_file.exists():
                with open(self.transcript_index_file, 'r', encoding='utf-8') as f:
                    data["transcript_index"] = json.load(f)
                self.logger.info(f"Loaded transcript index with {len(data['transcript_index'].get('transcripts', {}))} entries")
            
            # Load video mapping
            if self.video_mapping_file.exists():
                with open(self.video_mapping_file, 'r', encoding='utf-8') as f:
                    data["video_mapping"] = json.load(f)
                self.logger.info(f"Loaded {len(data['video_mapping'])} video mappings")
            
        except Exception as e:
            self.logger.error(f"Error loading existing data: {e}")
        
        return data
    
    def save_archive_data(self, data: Dict):
        """
        Save data back to archive files with backup
        
        Args:
            data: Dictionary containing all archive data
        """
        try:
            # Create backup directory
            backup_dir = self.archive_path / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup existing files
            for file_path in [self.videos_file, self.comments_file, self.keywords_file, self.transcript_index_file, self.video_mapping_file]:
                if file_path.exists():
                    shutil.copy2(file_path, backup_dir / file_path.name)
            
            # Save videos
            with open(self.videos_file, 'w', encoding='utf-8') as f:
                json.dump(data["videos"], f, indent=2, ensure_ascii=False)
            
            # Save comments
            with open(self.comments_file, 'w', encoding='utf-8') as f:
                json.dump(data["comments"], f, indent=2, ensure_ascii=False)
            
            # Save keywords
            with open(self.keywords_file, 'w', encoding='utf-8') as f:
                json.dump(data["keywords"], f, indent=2, ensure_ascii=False)
            
            # Save transcript index
            with open(self.transcript_index_file, 'w', encoding='utf-8') as f:
                json.dump(data["transcript_index"], f, indent=2, ensure_ascii=False)
            
            # Save video mapping
            with open(self.video_mapping_file, 'w', encoding='utf-8') as f:
                json.dump(data["video_mapping"], f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Archive data saved successfully (backup created: {backup_dir})")
            
        except Exception as e:
            self.logger.error(f"Error saving archive data: {e}")
            raise
    
    def check_for_new_videos(self) -> Dict:
        """
        Check for new videos and process them
        
        Returns:
            Processing results summary
        """
        with self.processing_lock:
            self.current_status = "checking_new_videos"
            
        try:
            self.logger.info("🔍 STEP 1: Starting new video check...")
            
            # Load existing data
            self.logger.info("📁 STEP 2: Loading existing archive data...")
            data = self.load_existing_data()
            self.logger.info(f"📊 Loaded {len(data['videos'])} existing videos, {len(data['comments'])} comments")
            
            # Find new videos
            self.logger.info("🔍 STEP 3: Checking YouTube for new videos...")
            new_videos = self.youtube_processor.find_new_videos(data["videos"])
            
            if not new_videos:
                self.logger.info("✅ No new videos found - archive is up to date")
                return {"new_videos": 0, "processed": 0, "errors": 0}
            
            self.logger.info(f"🎥 STEP 4: Found {len(new_videos)} new videos to process")
            for i, video in enumerate(new_videos, 1):
                self.logger.info(f"  📺 {i}. {video['title']} ({video['video_id']})")
            
            # Process new videos
            self.logger.info("⚙️ STEP 5: Starting video processing pipeline...")
            results = self.process_new_videos(new_videos, data)
            
            # Save updated data
            self.logger.info("💾 STEP 6: Saving updated archive data...")
            self.save_archive_data(data)
            
            self.logger.info(f"✅ New video check complete: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Error in new video check: {e}", exc_info=True)
            raise
        finally:
            with self.processing_lock:
                self.current_status = "idle"
    
    def process_new_videos(self, new_videos: List[Dict], data: Dict) -> Dict:
        """
        Process new videos: download, extract transcripts, generate summaries/keywords
        
        Args:
            new_videos: List of new video metadata
            data: Existing archive data (modified in place)
            
        Returns:
            Processing results summary
        """
        results = {"new_videos": len(new_videos), "processed": 0, "errors": 0}
        
        # Process videos with limited concurrency
        max_workers = min(self.config.get("max_concurrent", 3), len(new_videos))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all video processing jobs
            future_to_video = {
                executor.submit(self.process_single_video, video, data): video 
                for video in new_videos
            }
            
            # Process completed jobs
            for future in as_completed(future_to_video):
                video = future_to_video[future]
                try:
                    success = future.result()
                    if success:
                        results["processed"] += 1
                    else:
                        results["errors"] += 1
                        
                except Exception as e:
                    self.logger.error(f"Error processing video {video['video_id']}: {e}")
                    results["errors"] += 1
        
        return results
    
    def process_single_video(self, video_data: Dict, data: Dict) -> bool:
        """
        Process a single video completely - FULL PIPELINE
        
        COMPLETE PROCESSING PIPELINE:
        1. Download MP4 video file via yt-dlp
        2. Extract metadata (title, description, view_count, like_count, comment_count, published_at, etc.)
        3. Download transcript (VTT file) via yt-dlp
        4. Download ALL comments via YouTube Data API
        5. Process transcript through OpenAI GPT-4o-mini for summary
        6. Extract keywords via OpenAI GPT-4o-mini
        7. Save everything in archive-compatible format to /mnt/MM/MedicalMediumArchive/YouTube/MM_YT_archive/
        
        Args:
            video_data: Video metadata (includes video_id, title, description, view_count, like_count, comment_count, published_at, thumbnail_url, etc.)
            data: Archive data dictionary (thread-safe updates)
            
        Returns:
            True if successful, False otherwise
        """
        video_id = video_data['video_id']
        title = video_data['title']
        
        try:
            with self.processing_lock:
                self.current_status = f"processing_{video_id}"
                
            self.logger.info(f"🎬 PROCESSING VIDEO: {title} ({video_id})")
            self.logger.info(f"📊 Video metadata: views={video_data.get('view_count', 0)}, likes={video_data.get('like_count', 0)}, comments={video_data.get('comment_count', 0)}")
            self.logger.info(f"📅 Published: {video_data.get('published_at', 'Unknown')}")
            
            # STEP 1: Download video and transcript via yt-dlp
            self.logger.info(f"📥 STEP 1: Downloading video and transcript for {video_id}...")
            video_file, transcript_file = self.youtube_processor.download_video_with_transcript(
                video_id, self.videos_dir
            )
            
            if not video_file:
                self.logger.error(f"❌ Failed to download video {video_id}")
                return False
            
            self.logger.info(f"✅ Downloaded video: {video_file}")
            if transcript_file:
                self.logger.info(f"✅ Downloaded transcript: {transcript_file}")
            else:
                self.logger.warning(f"⚠️ No transcript available for {video_id}")
            
            # STEP 2: Update video metadata with file paths and archive info
            self.logger.info(f"📝 STEP 2: Updating video metadata...")
            video_data['file_path'] = f"videos/{video_file}"
            video_data['added_to_archive'] = datetime.now().isoformat()
            
            # STEP 3: Download ALL comments via YouTube Data API
            self.logger.info(f"💬 STEP 3: Downloading comments for {video_id}...")
            comments = self.youtube_processor.get_video_comments(video_id)
            self.logger.info(f"✅ Downloaded {len(comments)} comments")
            
            # STEP 4: Process transcript through OpenAI for summary and keywords
            transcript_text = ""
            summary_text = ""
            keywords = []
            
            if transcript_file:
                self.logger.info(f"🤖 STEP 4: Processing transcript through OpenAI GPT-4o-mini...")
                transcript_path = self.videos_dir / transcript_file
                
                self.logger.info(f"📄 Processing VTT file: {transcript_path}")
                transcript_text, summary_text, keywords = self.openai_processor.process_video_content(
                    video_data, transcript_path
                )
                
                self.logger.info(f"✅ Generated summary: {len(summary_text)} characters")
                self.logger.info(f"✅ Extracted keywords: {len(keywords)} keywords")
                self.logger.info(f"🔑 Keywords: {', '.join(keywords[:5])}..." if keywords else "🔑 No keywords extracted")
                
                # STEP 5: Save processed content to archive
                self.logger.info(f"💾 STEP 5: Saving processed content to archive...")
                self.openai_processor.save_processed_content(
                    video_data, transcript_text, summary_text, keywords, self.videos_dir
                )
                
                # Update processing flags
                video_data['has_transcript'] = bool(transcript_text)
                video_data['has_summary'] = bool(summary_text)
                self.logger.info(f"✅ Saved transcript ({len(transcript_text)} chars), summary ({len(summary_text)} chars)")
            else:
                self.logger.info(f"⏭️ STEP 4: Skipping transcript processing - no transcript available")
            
            # STEP 6: Update archive data structures (thread-safe) - MATCHING EXISTING FORMAT
            self.logger.info(f"🗂️ STEP 6: Updating archive data structures...")
            with self.processing_lock:
                # Add video to videos.json (matches existing format)
                data["videos"].append(video_data)
                self.logger.info(f"✅ Added video to videos.json")
                
                # Add comments to comments.json (matches existing format)
                data["comments"].extend(comments)
                self.logger.info(f"✅ Added {len(comments)} comments to comments.json")
                
                # Update video-mapping.json (matches existing format)
                data["video_mapping"][video_id] = {
                    "file_path": f"videos/{video_file}",
                    "title": title,
                    "added_at": video_data['added_to_archive']
                }
                self.logger.info(f"✅ Updated video-mapping.json")
                
                # Update transcript_index.json (matches existing format)
                if transcript_text:
                    safe_title = title.replace(":", "").replace("'", "").replace('"', '')
                    transcript_key = f"{safe_title}_{video_id}"
                    
                    data["transcript_index"]["transcripts"][transcript_key] = {
                        "video_id": video_id,
                        "title": title,
                        "transcript": transcript_text,
                        "processed_at": datetime.now().isoformat()
                    }
                    self.logger.info(f"✅ Updated transcript_index.json with key: {transcript_key}")
                
                # Update keywords.json (matches existing format)
                if keywords:
                    safe_title = title.replace(":", "").replace("'", "").replace('"', '')
                    keyword_patterns = [
                        f"{safe_title}_{video_id}",
                        f"{video_id}_{safe_title}",
                        f"{safe_title}_{video_id}_en_auto"
                    ]
                    
                    for pattern in keyword_patterns:
                        data["keywords"][pattern] = keywords
                    self.logger.info(f"✅ Updated keywords.json with {len(keyword_patterns)} patterns")
            
            # FINAL STATUS
            file_info = f"MP4: {video_file}"
            if transcript_file:
                file_info += f", VTT: {transcript_file}"
            if transcript_text:
                file_info += f", Summary: {len(summary_text)} chars"
            if keywords:
                file_info += f", Keywords: {len(keywords)}"
            
            self.logger.info(f"🎉 SUCCESSFULLY PROCESSED: {title}")
            self.logger.info(f"📁 Files created: {file_info}")
            self.logger.info(f"💬 Comments: {len(comments)}")
            self.logger.info(f"📍 Saved to: {self.videos_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ ERROR processing video {video_id} ({title}): {e}", exc_info=True)
            return False
    
    def update_existing_metadata(self) -> Dict:
        """
        Update metadata for existing videos (view counts, etc.)
        
        Returns:
            Update results summary
        """
        try:
            self.logger.info("Starting metadata update for existing videos...")
            
            # Load existing data
            data = self.load_existing_data()
            
            if not data["videos"]:
                self.logger.info("No existing videos to update")
                return {"updated": 0, "errors": 0}
            
            # Update metadata
            updated_videos = self.youtube_processor.update_video_metadata(data["videos"])
            data["videos"] = updated_videos
            
            # Save updated data
            self.save_archive_data(data)
            
            results = {"updated": len(updated_videos), "errors": 0}
            self.logger.info(f"Metadata update complete: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error updating metadata: {e}")
            return {"updated": 0, "errors": 1}
    
    def process_missing_transcripts(self) -> Dict:
        """
        Process videos that have VTT files but missing transcripts/summaries/keywords
        
        Returns:
            Processing results
        """
        try:
            self.logger.info("Processing missing transcripts and summaries...")
            
            # Load existing data
            data = self.load_existing_data()
            
            # Find videos with VTT files but missing processing
            videos_to_process = []
            
            for video in data["videos"]:
                video_id = video['video_id']
                
                # Check if VTT file exists
                vtt_files = list(self.videos_dir.glob(f"*{video_id}*.vtt"))
                
                if vtt_files and not video.get('has_transcript', False):
                    videos_to_process.append(video)
            
            if not videos_to_process:
                self.logger.info("No missing transcripts found")
                return {"processed": 0, "errors": 0}
            
            self.logger.info(f"Found {len(videos_to_process)} videos with missing transcripts")
            
            # Process missing content
            results = {"processed": 0, "errors": 0}
            
            for video_data in videos_to_process:
                video_id = video_data['video_id']
                
                try:
                    # Find VTT file
                    vtt_files = list(self.videos_dir.glob(f"*{video_id}*.vtt"))
                    if not vtt_files:
                        continue
                        
                    vtt_file = vtt_files[0]
                    
                    # Process content
                    transcript_text, summary_text, keywords = self.openai_processor.process_video_content(
                        video_data, vtt_file
                    )
                    
                    if transcript_text or summary_text:
                        # Save processed content
                        self.openai_processor.save_processed_content(
                            video_data, transcript_text, summary_text, keywords, self.videos_dir
                        )
                        
                        # Update video metadata
                        video_data['has_transcript'] = bool(transcript_text)
                        video_data['has_summary'] = bool(summary_text)
                        
                        # Update archive structures
                        self._update_archive_structures(video_data, data, transcript_text, keywords)
                        
                        results["processed"] += 1
                        self.logger.info(f"Processed missing content for: {video_data['title']}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing missing content for {video_id}: {e}")
                    results["errors"] += 1
            
            # Save updated data
            if results["processed"] > 0:
                self.save_archive_data(data)
            
            self.logger.info(f"Missing transcript processing complete: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing missing transcripts: {e}")
            return {"processed": 0, "errors": 1}
    
    def _update_archive_structures(self, video_data: Dict, data: Dict, transcript_text: str, keywords: List[str]):
        """
        Update archive data structures with processed content
        
        Args:
            video_data: Video metadata
            data: Archive data dictionary
            transcript_text: Processed transcript
            keywords: Extracted keywords
        """
        video_id = video_data['video_id']
        title = video_data['title']
        
        # Update transcript index
        if transcript_text:
            safe_title = title.replace(":", "").replace("'", "").replace('"', '')
            transcript_key = f"{safe_title}_{video_id}"
            
            data["transcript_index"]["transcripts"][transcript_key] = {
                "video_id": video_id,
                "title": title,
                "transcript": transcript_text,
                "processed_at": datetime.now().isoformat()
            }
        
        # Update keywords
        if keywords:
            safe_title = title.replace(":", "").replace("'", "").replace('"', '')
            keyword_patterns = [
                f"{safe_title}_{video_id}",
                f"{video_id}_{safe_title}",
                f"{safe_title}_{video_id}_en_auto"
            ]
            
            for pattern in keyword_patterns:
                data["keywords"][pattern] = keywords
    
    def get_status(self) -> Dict:
        """
        Get current processing status and archive statistics
        
        Returns:
            Status dictionary
        """
        data = self.load_existing_data()
        
        return {
            "status": self.current_status,
            "total_videos": len(data["videos"]),
            "total_comments": len(data["comments"]),
            "videos_with_transcripts": sum(1 for v in data["videos"] if v.get("has_transcript")),
            "videos_with_summaries": sum(1 for v in data["videos"] if v.get("has_summary")),
            "keyword_entries": len(data["keywords"]),
            "last_update": max((v.get("scraped_at", "") for v in data["videos"]), default="Never"),
            "archive_path": str(self.archive_path)
        }