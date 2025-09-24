# Medical Medium YouTube Archive Manager

A comprehensive Python application for automatically downloading, processing, and managing YouTube videos with GUI interface, scheduling, and AI-powered content analysis.

## Features

- 🎥 **Automated Video Discovery**: Uses YouTube Data API to find new videos from configured channels
- 📥 **Smart Downloads**: Downloads videos and subtitles using yt-dlp with configurable quality
- 🤖 **AI Processing**: Uses OpenAI GPT-4o-mini to generate summaries and extract keywords from transcripts
- 💬 **Comment Archival**: Downloads and stores all video comments with metadata
- 📊 **GUI Interface**: User-friendly interface for monitoring and controlling the archive process
- ⏰ **Automatic Scheduling**: Runs daily checks at midnight with system startup integration
- 📁 **Archive Compatibility**: Maintains compatibility with existing Medical Medium archive structure
- 🔄 **Incremental Updates**: Only processes new content, updates metadata for existing videos
- 📝 **Comprehensive Logging**: Detailed logging with GUI log viewer
- 🛠️ **Manual Controls**: Manual triggers for checking, updating, and processing content

## Architecture

The application consists of several key modules:

### Core Components

1. **youtube_archive_manager.py** - Main GUI application with scheduler
2. **youtube_processor.py** - YouTube Data API integration and yt-dlp wrapper
3. **openai_processor.py** - OpenAI API integration for content processing
4. **archive_manager.py** - Data management and archive coordination

### Data Flow

1. **Discovery**: YouTube Data API finds new videos and metadata
2. **Download**: yt-dlp downloads video files and VTT subtitle files
3. **Processing**: OpenAI processes transcripts to generate summaries and keywords
4. **Integration**: New data is merged with existing archive structure
5. **Storage**: All data saved in JSON files matching existing format

## Installation

### Prerequisites

- Python 3.8 or higher
- YouTube Data API key
- OpenAI API key
- Sufficient storage space for video files

### Setup Steps

1. **Clone/Copy Files**
   ```bash
   # Copy all Python files to /home/mm/ or your preferred directory
   cd /home/mm
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API Keys**
   - Run the application: `python youtube_archive_manager.py`
   - Go to the "Configuration" tab
   - Enter your YouTube Data API key
   - Enter your OpenAI API key
   - Set archive path (default: `/mnt/MM/MedicalMediumArchive/YouTube/MM_YT_archive`)
   - Click "Save Configuration"

4. **Install System Service (Optional)**
   ```bash
   bash install_startup_service.sh
   ```

## Configuration

### API Keys

#### YouTube Data API Key
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable YouTube Data API v3
4. Create API credentials (API Key)
5. Restrict key to YouTube Data API v3

#### OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create account or sign in
3. Generate API key in API Keys section
4. Ensure sufficient credits for GPT-4o-mini usage

### Archive Settings

- **Archive Path**: Directory where all files will be stored
- **Channel ID**: YouTube channel ID to monitor (default: Medical Medium)
- **Download Quality**: Video quality preference (best, 1080p, 720p, worst)
- **Max Concurrent**: Number of simultaneous downloads (1-10)

### Scheduler Settings

- **Auto Start**: Automatically start scheduler on application launch
- **Daily Check Time**: Time for daily automated checks (HH:MM format)

## Usage

### GUI Mode

```bash
python youtube_archive_manager.py
```

### Command Line Options

```bash
# Check for new videos once and exit
python youtube_archive_manager.py --check-only

# Run in headless mode (background service)
python youtube_archive_manager.py --headless

# Use custom config file
python youtube_archive_manager.py --config /path/to/config.json
```

### System Service

```bash
# Start service
sudo systemctl start youtube-archive-manager

# Stop service
sudo systemctl stop youtube-archive-manager

# Check status
sudo systemctl status youtube-archive-manager

# View logs
journalctl -u youtube-archive-manager -f
```

## GUI Interface

### Main Control Tab

- **Archive Status**: Shows video/comment counts, last update, next scheduled check
- **Manual Controls**: Buttons for immediate actions
- **Progress Monitor**: Real-time progress display and activity log

### Configuration Tab

- **API Configuration**: YouTube and OpenAI API key settings
- **Archive Settings**: Path, channel, and download preferences
- **Scheduler Settings**: Automation and timing configuration

### Logs Tab

- **Log Viewer**: Real-time log display with refresh and clear options
- **Error Tracking**: Detailed error information and troubleshooting

## File Structure

### Generated Files

```
archive_path/
├── videos.json              # Video metadata (compatible with existing)
├── comments.json            # All comments (compatible with existing)
├── keywords.json            # Extracted keywords (compatible with existing)
├── transcript_index.json    # Transcript data (compatible with existing)
├── video-mapping.json       # File path mappings
├── videos/
│   ├── [Title]_[VideoID].mp4       # Downloaded videos
│   ├── [Title]_[VideoID].en.vtt    # Subtitle files
│   ├── [Title]_[VideoID]_transcript.txt  # Processed transcripts
│   ├── [Title]_[VideoID]_summary.txt     # AI-generated summaries
│   └── [Title]_[VideoID]_metadata.json   # Processing metadata
├── logs/
│   └── archive_manager.log  # Application logs
└── backups/
    └── [timestamp]/         # Automatic backups before updates
```

### Configuration File

```json
{
  "archive_path": "/mnt/MM/MedicalMediumArchive/YouTube/MM_YT_archive",
  "channel_id": "UCUORv_qpgmg8N5plVqlYjXg",
  "youtube_api_key": "your_youtube_api_key",
  "openai_api_key": "your_openai_api_key",
  "auto_start": true,
  "check_time": "00:00",
  "download_quality": "best",
  "max_concurrent": 3
}
```

## Processing Pipeline

### New Video Discovery

1. **API Query**: YouTube Data API retrieves channel's upload playlist
2. **Comparison**: New videos identified by comparing with existing archive
3. **Metadata Extraction**: Video details, statistics, and thumbnails collected

### Content Download

1. **Video Download**: yt-dlp downloads video file in specified quality
2. **Subtitle Extraction**: Automatic and manual subtitles downloaded as VTT
3. **Comment Collection**: YouTube Data API retrieves all comments and replies

### AI Processing

1. **Transcript Cleaning**: VTT files processed to extract clean text
2. **Summary Generation**: GPT-4o-mini creates comprehensive summaries
3. **Keyword Extraction**: AI identifies relevant keywords and topics

### Archive Integration

1. **Data Merging**: New content merged with existing archive data
2. **Index Updates**: Transcript and keyword indexes updated
3. **File Management**: Consistent naming and organization maintained

## Troubleshooting

### Common Issues

**API Authentication Errors**
- Verify API keys are correct and active
- Check API quotas and billing status
- Ensure proper API permissions

**Download Failures**
- Check internet connectivity
- Verify video availability (not private/deleted)
- Monitor disk space

**Processing Errors**
- Check OpenAI API credits
- Verify file permissions
- Review logs for specific errors

### Log Analysis

```bash
# View recent logs
tail -f /path/to/archive/logs/archive_manager.log

# Search for errors
grep -i error /path/to/archive/logs/archive_manager.log

# Monitor system service
journalctl -u youtube-archive-manager -f
```

### Performance Optimization

- **Concurrent Downloads**: Adjust `max_concurrent` based on bandwidth
- **Quality Settings**: Lower quality reduces download time and storage
- **Schedule Timing**: Run during off-peak hours to avoid rate limits

## Data Compatibility

This application maintains full compatibility with existing Medical Medium archive structures:

- **Video Format**: Matches existing videos.json schema
- **Comment Format**: Compatible with existing comments.json structure
- **Keyword Structure**: Uses same keyword mapping patterns
- **File Naming**: Follows existing naming conventions

## Support

### Error Reporting

Include the following when reporting issues:
- Application logs from GUI or system service
- Configuration settings (redacted API keys)
- Error messages and stack traces
- System information (OS, Python version)

### Contributing

This is a specialized application for Medical Medium archive management. Contributions should focus on:
- Performance improvements
- Error handling enhancements
- Additional AI processing features
- Archive format compatibility

## License

This application is designed specifically for Medical Medium content archival and educational purposes.