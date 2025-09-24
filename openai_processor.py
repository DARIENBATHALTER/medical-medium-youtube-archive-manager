"""
OpenAI Processing Module
Handles transcript processing, summary generation, and keyword extraction
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import openai
from openai import OpenAI

class OpenAIProcessor:
    """Handles OpenAI API interactions for content processing"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.client = None
        self.logger = logging.getLogger(__name__)
        self.initialize_client()
    
    def initialize_client(self):
        """Initialize OpenAI client"""
        if self.config.get("openai_api_key"):
            try:
                self.client = OpenAI(api_key=self.config["openai_api_key"])
                self.logger.info("OpenAI client initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize OpenAI client: {e}")
                raise
        else:
            raise ValueError("OpenAI API key not configured")
    
    def process_transcript_file(self, vtt_file_path: Path) -> str:
        """
        Process VTT transcript file and extract clean text
        
        Args:
            vtt_file_path: Path to VTT transcript file
            
        Returns:
            Clean transcript text
        """
        try:
            with open(vtt_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove VTT headers and timestamps
            lines = content.split('\n')
            transcript_lines = []
            
            skip_next = False
            for line in lines:
                line = line.strip()
                
                # Skip VTT header
                if line.startswith('WEBVTT'):
                    continue
                
                # Skip timestamp lines (contain --> )
                if '-->' in line:
                    skip_next = False
                    continue
                
                # Skip empty lines
                if not line:
                    continue
                
                # Skip lines that look like timestamps (numbers only)
                if line.isdigit():
                    skip_next = True
                    continue
                
                if skip_next:
                    skip_next = False
                    continue
                
                # Clean up the line
                line = re.sub(r'<[^>]+>', '', line)  # Remove HTML tags
                line = re.sub(r'\s+', ' ', line).strip()  # Normalize spaces
                
                if line:
                    transcript_lines.append(line)
            
            # Join and clean up the transcript
            transcript = ' '.join(transcript_lines)
            transcript = re.sub(r'\s+', ' ', transcript).strip()
            
            self.logger.info(f"Processed transcript: {len(transcript)} characters")
            return transcript
            
        except Exception as e:
            self.logger.error(f"Error processing transcript file {vtt_file_path}: {e}")
            return ""
    
    def generate_summary(self, transcript: str, video_title: str) -> str:
        """
        Generate summary using OpenAI GPT-4o-mini
        
        Args:
            transcript: Video transcript text
            video_title: Video title for context
            
        Returns:
            Generated summary text
        """
        if not transcript:
            self.logger.warning("Empty transcript provided for summary generation")
            return ""
        
        try:
            # Truncate transcript if too long (GPT-4o-mini has token limits)
            max_chars = 12000  # Conservative estimate for token limits
            if len(transcript) > max_chars:
                transcript = transcript[:max_chars] + "..."
                self.logger.info(f"Truncated transcript to {max_chars} characters")
            
            # Create summary prompt
            prompt = f"""Please analyze the following video transcript from a Medical Medium episode titled "{video_title}" and create a comprehensive summary.

The summary should:
1. Capture the main health topics and healing advice discussed
2. Include key medical insights and recommendations
3. Highlight important information about chronic illness, symptoms, or healing protocols
4. Maintain the spiritual and empowering tone of the content
5. Be structured and easy to read
6. Be approximately 200-400 words

Transcript:
{transcript}

Please provide a well-structured summary:"""

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at summarizing Medical Medium content with focus on health, healing, and spiritual wellness. Create accurate, comprehensive summaries that capture the essence of the healing guidance provided."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.3,  # Lower temperature for more consistent summaries
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            summary = response.choices[0].message.content.strip()
            self.logger.info(f"Generated summary: {len(summary)} characters")
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating summary: {e}")
            return ""
    
    def extract_keywords(self, transcript: str, summary: str, video_title: str) -> List[str]:
        """
        Extract keywords using OpenAI GPT-4o-mini
        
        Args:
            transcript: Video transcript text
            summary: Generated summary text
            video_title: Video title for context
            
        Returns:
            List of extracted keywords
        """
        if not summary and not transcript:
            self.logger.warning("No content provided for keyword extraction")
            return []
        
        try:
            # Use summary preferentially, fall back to transcript excerpt
            content = summary if summary else transcript[:3000]
            
            # Create keyword extraction prompt
            prompt = f"""Based on the following Medical Medium content from "{video_title}", extract the most important and relevant keywords and phrases.

Focus on extracting:
1. Health conditions, symptoms, and diseases mentioned
2. Healing foods, supplements, and protocols
3. Body systems and organs discussed
4. Emotional and spiritual healing concepts
5. Key Medical Medium terminology
6. Important health advice and insights

Extract 15-25 keywords/phrases that best represent this content. Return them as a simple comma-separated list.

Content:
{content}

Keywords:"""

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting relevant keywords from Medical Medium content. Focus on health conditions, healing foods, supplements, body systems, and key healing concepts."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.2,  # Low temperature for consistent extraction
                top_p=1.0,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            keywords_text = response.choices[0].message.content.strip()
            
            # Parse keywords from response
            keywords = []
            for keyword in keywords_text.split(','):
                keyword = keyword.strip().strip('"').strip("'")
                if keyword and len(keyword) > 2:
                    keywords.append(keyword)
            
            # Clean up and deduplicate
            keywords = list(dict.fromkeys(keywords))  # Remove duplicates while preserving order
            keywords = [kw for kw in keywords if len(kw.split()) <= 4]  # Remove overly long phrases
            
            self.logger.info(f"Extracted {len(keywords)} keywords")
            return keywords[:25]  # Limit to 25 keywords
            
        except Exception as e:
            self.logger.error(f"Error extracting keywords: {e}")
            return []
    
    def process_video_content(self, video_data: Dict, vtt_file_path: Path) -> Tuple[str, str, List[str]]:
        """
        Complete processing pipeline for a video
        
        Args:
            video_data: Video metadata dictionary
            vtt_file_path: Path to VTT transcript file
            
        Returns:
            Tuple of (transcript, summary, keywords)
        """
        self.logger.info(f"Processing content for video: {video_data['title']}")
        
        # Step 1: Process transcript
        transcript = self.process_transcript_file(vtt_file_path)
        if not transcript:
            self.logger.warning(f"No transcript available for {video_data['video_id']}")
            return "", "", []
        
        # Step 2: Generate summary
        summary = self.generate_summary(transcript, video_data['title'])
        
        # Step 3: Extract keywords
        keywords = self.extract_keywords(transcript, summary, video_data['title'])
        
        self.logger.info(f"Content processing complete for {video_data['video_id']}")
        return transcript, summary, keywords
    
    def save_processed_content(self, video_data: Dict, transcript: str, summary: str, keywords: List[str], output_path: Path):
        """
        Save processed content to files matching archive structure
        
        Args:
            video_data: Video metadata
            transcript: Processed transcript text
            summary: Generated summary
            keywords: Extracted keywords
            output_path: Base output directory
        """
        video_id = video_data['video_id']
        title = video_data['title']
        
        # Create filename base (matching existing pattern)
        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = re.sub(r'\s+', ' ', safe_title).strip()
        filename_base = f"{safe_title}_{video_id}"
        
        try:
            # Save transcript as .txt
            if transcript:
                transcript_file = output_path / f"{filename_base}_transcript.txt"
                with open(transcript_file, 'w', encoding='utf-8') as f:
                    f.write(f"Video: {title}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(transcript)
                self.logger.info(f"Saved transcript: {transcript_file}")
            
            # Save summary as .txt
            if summary:
                summary_file = output_path / f"{filename_base}_summary.txt"
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write(f"Video: {title}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(summary)
                self.logger.info(f"Saved summary: {summary_file}")
            
            # Save metadata as JSON sidecar
            metadata_file = output_path / f"{filename_base}_metadata.json"
            metadata = {
                **video_data,
                "processed_at": datetime.now().isoformat(),
                "has_transcript": bool(transcript),
                "has_summary": bool(summary),
                "keyword_count": len(keywords),
                "transcript_length": len(transcript),
                "summary_length": len(summary)
            }
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved metadata: {metadata_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving processed content for {video_id}: {e}")
    
    def batch_process_videos(self, video_list: List[Dict], vtt_files_path: Path, output_path: Path) -> Dict[str, Dict]:
        """
        Process multiple videos in batch
        
        Args:
            video_list: List of video metadata dictionaries
            vtt_files_path: Directory containing VTT files
            output_path: Output directory for processed content
            
        Returns:
            Dictionary mapping video_id to processing results
        """
        results = {}
        
        for i, video_data in enumerate(video_list, 1):
            video_id = video_data['video_id']
            title = video_data['title']
            
            self.logger.info(f"Processing video {i}/{len(video_list)}: {title}")
            
            # Find VTT file
            vtt_files = list(vtt_files_path.glob(f"*{video_id}*.vtt"))
            if not vtt_files:
                self.logger.warning(f"No VTT file found for {video_id}")
                results[video_id] = {"error": "No VTT file found"}
                continue
            
            vtt_file = vtt_files[0]
            
            try:
                # Process the content
                transcript, summary, keywords = self.process_video_content(video_data, vtt_file)
                
                # Save processed content
                self.save_processed_content(video_data, transcript, summary, keywords, output_path)
                
                # Store results
                results[video_id] = {
                    "success": True,
                    "transcript_length": len(transcript),
                    "summary_length": len(summary),
                    "keyword_count": len(keywords),
                    "keywords": keywords
                }
                
            except Exception as e:
                self.logger.error(f"Error processing {video_id}: {e}")
                results[video_id] = {"error": str(e)}
        
        self.logger.info(f"Batch processing complete: {len(results)} videos processed")
        return results