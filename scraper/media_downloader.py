"""
Media Downloader for ED Data Express

This module handles downloading and organizing media files such as images,
videos, PDFs, and other files from the ED Data Express website.
"""

import os
import logging
import requests
import mimetypes
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("media_downloader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("media_downloader")

class MediaDownloader:
    """Downloader for media files from ED Data Express website."""
    
    def __init__(self, base_url="https://eddataexpress.ed.gov/", output_dir="data/media"):
        """
        Initialize the media downloader.
        
        Args:
            base_url: Root URL of the ED Data Express website
            output_dir: Directory to save downloaded media files
        """
        self.base_url = base_url
        self.output_dir = output_dir
        self.domain = urlparse(base_url).netloc
        self.downloaded_urls = set()
        
        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "videos"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "documents"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "other"), exist_ok=True)
    
    def get_media_type(self, url, content_type=None):
        """
        Determine the media type based on URL and content type.
        
        Args:
            url: URL of the media file
            content_type: Content-Type header from the response
            
        Returns:
            Media type category (images, videos, documents, other)
        """
        # Check content type first if available
        if content_type:
            if content_type.startswith("image/"):
                return "images"
            elif content_type.startswith("video/"):
                return "videos"
            elif content_type in [
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-powerpoint",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ]:
                return "documents"
        
        # Fallback to URL extension
        path = urlparse(url).path.lower()
        if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico")):
            return "images"
        elif path.endswith((".mp4", ".webm", ".ogg", ".mov", ".avi")):
            return "videos"
        elif path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")):
            return "documents"
        
        return "other"
    
    def url_to_filename(self, url):
        """Convert URL to a valid filename, preserving the original extension."""
        # Extract the path and remove query parameters
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # Get the filename from the path
        filename = os.path.basename(path)
        
        # If filename is empty, use a hash of the URL
        if not filename:
            filename = f"file_{hash(url) % 10000:04d}"
            
            # Try to get an extension from content type
            content_type = mimetypes.guess_type(url)[0]
            if content_type:
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    filename += ext
        
        # Replace problematic characters
        filename = filename.replace("?", "_").replace("&", "_").replace("=", "_")
        
        return filename
    
    def download_media(self, url):
        """
        Download a media file.
        
        Args:
            url: URL of the media file to download
            
        Returns:
            Path to the saved file or None if download failed
        """
        # Skip if already downloaded
        if url in self.downloaded_urls:
            return None
        
        try:
            # Download the file
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get content type and size
            content_type = response.headers.get("Content-Type")
            file_size = int(response.headers.get("Content-Length", 0))
            
            # Determine media type and filename
            media_type = self.get_media_type(url, content_type)
            filename = self.url_to_filename(url)
            
            # Create output path
            output_path = os.path.join(self.output_dir, media_type, filename)
            
            # Download with progress bar
            with open(output_path, "wb") as f, tqdm(
                desc=f"Downloading {filename}",
                total=file_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
            
            self.downloaded_urls.add(url)
            logger.info(f"Downloaded media: {url} -> {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error downloading media {url}: {str(e)}")
            return None
    
    def extract_media_from_html(self, html_file, base_url):
        """
        Extract media URLs from an HTML file.
        
        Args:
            html_file: Path to the HTML file to scan
            base_url: Base URL for resolving relative links
            
        Returns:
            List of media URLs found
        """
        media_urls = []
        
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            
            # Extract image URLs
            for img in soup.find_all("img", src=True):
                src = urljoin(base_url, img["src"])
                media_urls.append(src)
            
            # Extract video URLs
            for video in soup.find_all("video"):
                # Check source tags
                for source in video.find_all("source", src=True):
                    src = urljoin(base_url, source["src"])
                    media_urls.append(src)
                
                # Check video src attribute
                if video.get("src"):
                    src = urljoin(base_url, video["src"])
                    media_urls.append(src)
            
            # Extract audio URLs
            for audio in soup.find_all("audio"):
                # Check source tags
                for source in audio.find_all("source", src=True):
                    src = urljoin(base_url, source["src"])
                    media_urls.append(src)
                
                # Check audio src attribute
                if audio.get("src"):
                    src = urljoin(base_url, audio["src"])
                    media_urls.append(src)
            
            # Extract object and embed tags
            for obj in soup.find_all(["object", "embed"], src=True):
                src = urljoin(base_url, obj["src"])
                media_urls.append(src)
            
            # Extract links to documents
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Check if it's a document link
                if href.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")):
                    src = urljoin(base_url, href)
                    media_urls.append(src)
            
            return media_urls
            
        except Exception as e:
            logger.error(f"Error extracting media from {html_file}: {str(e)}")
            return []
    
    def process_html_directory(self, html_dir, base_url):
        """
        Process all HTML files in a directory to extract and download media.
        
        Args:
            html_dir: Directory containing HTML files
            base_url: Base URL for resolving relative links
        """
        # Ensure html_dir exists
        if not os.path.exists(html_dir):
            logger.error(f"HTML directory does not exist: {html_dir}")
            return
        
        # Get list of HTML files
        html_files = [
            os.path.join(html_dir, f) for f in os.listdir(html_dir)
            if f.endswith(".html") and os.path.isfile(os.path.join(html_dir, f))
        ]
        
        logger.info(f"Found {len(html_files)} HTML files to process")
        
        # Process each HTML file
        for html_file in tqdm(html_files, desc="Processing HTML files"):
            # Extract media URLs
            media_urls = self.extract_media_from_html(html_file, base_url)
            
            # Download each media file
            for url in media_urls:
                # Only download from the same domain
                if urlparse(url).netloc == self.domain:
                    self.download_media(url)


if __name__ == "__main__":
    # Example usage
    downloader = MediaDownloader()
    downloader.process_html_directory("data/raw/html", "https://eddataexpress.ed.gov/") 