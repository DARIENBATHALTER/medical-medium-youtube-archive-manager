"""
YouTube Video Processing Module
Handles video discovery, download, and metadata extraction
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re

import yt_dlp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class YouTubeProcessor:
    """Handles YouTube video discovery and processing"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.youtube = None
        self.logger = logging.getLogger(__name__)
        self.initialize_api()
    
    def initialize_api(self):
        """Initialize YouTube Data API"""
        if self.config.get("youtube_api_key"):
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.config["youtube_api_key"])
                self.logger.info("YouTube API initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize YouTube API: {e}")
                raise
        else:
            raise ValueError("YouTube API key not configured")
    
    def get_channel_videos(self, channel_id: str, max_results: int = 50) -> List[Dict]:
        """
        Get all videos from a channel using YouTube Data API
        
        Args:
            channel_id: YouTube channel ID
            max_results: Maximum results per API call
            
        Returns:
            List of video metadata dictionaries
        """
        all_videos = []
        next_page_token = None
        
        try:
            while True:
                # Get playlist ID for channel uploads
                channel_response = self.youtube.channels().list(
                    part='contentDetails',
                    id=channel_id
                ).execute()
                
                if not channel_response['items']:
                    self.logger.error(f"Channel {channel_id} not found")
                    return []
                
                uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                
                # Get videos from uploads playlist
                playlist_response = self.youtube.playlistItems().list(
                    part='snippet',
                    playlistId=uploads_playlist_id,
                    maxResults=max_results,
                    pageToken=next_page_token
                ).execute()
                
                video_ids = []
                for item in playlist_response['items']:
                    video_ids.append(item['snippet']['resourceId']['videoId'])
                
                # Get detailed video information
                if video_ids:
                    videos_response = self.youtube.videos().list(
                        part='snippet,statistics,contentDetails',
                        id=','.join(video_ids)
                    ).execute()
                    
                    for video in videos_response['items']:
                        video_data = self._extract_video_metadata(video)
                        all_videos.append(video_data)
                
                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token:
                    break
                    
                self.logger.info(f"Retrieved {len(all_videos)} videos so far...")
        
        except HttpError as e:
            self.logger.error(f"YouTube API error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error retrieving channel videos: {e}")
            raise
        
        self.logger.info(f"Total videos retrieved: {len(all_videos)}")
        return all_videos
    
    def _extract_video_metadata(self, video_data: Dict) -> Dict:
        """
        Extract COMPLETE metadata from YouTube API video response
        EXTRACTS: video_id, title, description, published_at, view_count, like_count, comment_count, thumbnail_url, channel_id
        
        Args:
            video_data: Raw video data from YouTube API
            
        Returns:
            Formatted video metadata dictionary - MATCHES EXISTING ARCHIVE FORMAT
        """
        snippet = video_data['snippet']
        statistics = video_data.get('statistics', {})
        
        # Parse published date
        published_at = datetime.fromisoformat(
            snippet['publishedAt'].replace('Z', '+00:00')
        ).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Extract all metadata (matching existing archive format)
        metadata = {
            "video_id": video_data['id'],  # VIDEO SHORTCODE/ID
            "title": snippet['title'],
            "description": snippet['description'],  # FULL DESCRIPTION
            "published_at": published_at,  # UPLOAD DATE
            "channel_id": snippet['channelId'],
            "view_count": int(statistics.get('viewCount', 0)),  # VIEW COUNT
            "like_count": int(statistics.get('likeCount', 0)),  # LIKE COUNT  
            "comment_count": int(statistics.get('commentCount', 0)),  # COMMENT COUNT
            "scraped_at": datetime.now().isoformat(),
            "thumbnail_url": snippet['thumbnails'].get('high', {}).get('url', ''),
            "file_path": None,  # Will be set after download
            "added_to_archive": None,  # Will be set when added to archive
            "has_transcript": False,  # Will be updated after transcript processing
            "has_summary": False,  # Will be updated after summary generation
            "sync_id": f"auto_{int(datetime.now().timestamp())}"
        }
        
        # Log extracted metadata
        self.logger.info(f"📊 Extracted metadata for {metadata['video_id']}:")
        self.logger.info(f"   📺 Title: {metadata['title']}")
        self.logger.info(f"   📅 Published: {metadata['published_at']}")
        self.logger.info(f"   👀 Views: {metadata['view_count']:,}")
        self.logger.info(f"   👍 Likes: {metadata['like_count']:,}")  
        self.logger.info(f"   💬 Comments: {metadata['comment_count']:,}")
        self.logger.info(f"   📝 Description length: {len(metadata['description'])} chars")
        
        return metadata
    
    def get_video_comments(self, video_id: str) -> List[Dict]:
        """
        Get all comments for a video using YouTube Data API
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            List of comment dictionaries
        """
        comments = []
        next_page_token = None
        
        try:
            while True:
                response = self.youtube.commentThreads().list(
                    part='snippet,replies',
                    videoId=video_id,
                    maxResults=100,
                    order='relevance',
                    pageToken=next_page_token
                ).execute()
                
                for item in response['items']:
                    # Main comment
                    comment = self._extract_comment_data(item['snippet']['topLevelComment'], video_id)
                    comments.append(comment)
                    
                    # Replies (if any)
                    if 'replies' in item:
                        for reply in item['replies']['comments']:
                            reply_data = self._extract_comment_data(reply, video_id, parent_id=comment['comment_id'])
                            comments.append(reply_data)
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
                    
        except HttpError as e:
            if e.resp.status == 403:
                self.logger.warning(f"Comments disabled for video {video_id}")
            else:
                self.logger.error(f"Error getting comments for {video_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error getting comments for {video_id}: {e}")
        
        self.logger.info(f"Retrieved {len(comments)} comments for video {video_id}")
        return comments
    
    def _extract_comment_data(self, comment_data: Dict, video_id: str, parent_id: str = None) -> Dict:
        """
        Extract comment metadata from YouTube API response
        
        Args:
            comment_data: Raw comment data from YouTube API
            video_id: Video ID this comment belongs to
            parent_id: Parent comment ID if this is a reply
            
        Returns:
            Formatted comment dictionary
        """
        snippet = comment_data['snippet']
        
        # Parse published date
        published_at = datetime.fromisoformat(
            snippet['publishedAt'].replace('Z', '+00:00')
        ).strftime('%Y-%m-%d %H:%M:%S+00:00')
        
        return {
            "comment_id": comment_data['id'],
            "video_id": video_id,
            "parent_comment_id": parent_id,
            "author": snippet['authorDisplayName'],
            "author_channel_id": snippet.get('authorChannelId', {}).get('value', ''),
            "text": snippet['textDisplay'],
            "published_at": published_at,
            "like_count": snippet['likeCount'],
            "is_reply": 1 if parent_id else 0,
            "scraped_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        }
    
    def download_video_with_transcript(self, video_id: str, output_path: Path) -> Tuple[Optional[str], Optional[str]]:
        """
        Download video and transcript using yt-dlp
        
        Args:
            video_id: YouTube video ID
            output_path: Directory to save files
            
        Returns:
            Tuple of (video_filename, transcript_filename) or (None, None) if failed
        """
        try:
            # Create output directory
            output_path.mkdir(parents=True, exist_ok=True)
            
            # yt-dlp options
            ydl_opts = {
                'format': self.config.get('download_quality', 'best[height<=1080]'),
                'outtmpl': str(output_path / '%(title)s_%(id)s.%(ext)s'),
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitlesformat': 'vtt',
                'subtitleslangs': ['en'],
                'ignoreerrors': True,
                'no_warnings': False,
                'extractaudio': False,
                'audioformat': 'mp3',
                'embed_subs': False,
                'writeinfojson': True,  # Save metadata as JSON sidecar
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Download video and subtitles
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Get info first to determine filename
                info = ydl.extract_info(video_url, download=False)
                title = self._sanitize_filename(info['title'])
                
                # Download
                ydl.download([video_url])
                
                # Find downloaded files
                video_file = None
                transcript_file = None
                
                for file in output_path.glob(f"*{video_id}*"):
                    if file.suffix == '.mp4':
                        video_file = file.name
                    elif file.suffix == '.vtt' and '.en.' in file.name:
                        transcript_file = file.name
                
                self.logger.info(f"Downloaded video {video_id}: {video_file}")
                if transcript_file:
                    self.logger.info(f"Downloaded transcript: {transcript_file}")
                else:
                    self.logger.warning(f"No transcript found for video {video_id}")
                
                return video_file, transcript_file
                
        except Exception as e:
            self.logger.error(f"Error downloading video {video_id}: {e}")
            return None, None
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for filesystem compatibility
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace problematic characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'\s+', ' ', filename).strip()
        return filename[:200]  # Limit length
    
    def find_new_videos(self, existing_videos: List[Dict]) -> List[Dict]:
        """
        Find new videos by comparing with existing archive
        
        Args:
            existing_videos: List of existing video metadata
            
        Returns:
            List of new video metadata
        """
        existing_ids = {video['video_id'] for video in existing_videos}
        
        # Get all current videos from channel
        channel_videos = self.get_channel_videos(self.config['channel_id'])
        
        # Filter out existing videos
        new_videos = [video for video in channel_videos if video['video_id'] not in existing_ids]
        
        self.logger.info(f"Found {len(new_videos)} new videos")
        return new_videos
    
    def update_video_metadata(self, existing_videos: List[Dict]) -> List[Dict]:
        """
        Update metadata for existing videos (view counts, like counts, etc.)
        
        Args:
            existing_videos: List of existing video metadata
            
        Returns:
            List of updated video metadata
        """
        updated_videos = []
        
        # Process in batches of 50 (API limit)
        for i in range(0, len(existing_videos), 50):
            batch = existing_videos[i:i+50]
            video_ids = [video['video_id'] for video in batch]
            
            try:
                # Get current stats from API
                response = self.youtube.videos().list(
                    part='statistics',
                    id=','.join(video_ids)
                ).execute()
                
                # Update stats
                stats_by_id = {item['id']: item['statistics'] for item in response['items']}
                
                for video in batch:
                    video_id = video['video_id']
                    if video_id in stats_by_id:
                        stats = stats_by_id[video_id]
                        video['view_count'] = int(stats.get('viewCount', 0))
                        video['like_count'] = int(stats.get('likeCount', 0))
                        video['comment_count'] = int(stats.get('commentCount', 0))
                        video['scraped_at'] = datetime.now().isoformat()
                    
                    updated_videos.append(video)
                    
            except Exception as e:
                self.logger.error(f"Error updating metadata batch: {e}")
                updated_videos.extend(batch)  # Add unchanged if error
        
        self.logger.info(f"Updated metadata for {len(updated_videos)} videos")
        return updated_videos