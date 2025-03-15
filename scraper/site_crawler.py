"""
Site Crawler for ED Data Express

This module handles crawling the ED Data Express website to download HTML files,
discover links to JS, CSS, and other resources.
"""

import os
import re
import time
import logging
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("site_crawler")

class EDDataExpressCrawler:
    """Crawler for ED Data Express website."""
    
    def __init__(self, base_url="https://eddataexpress.ed.gov/", output_dir="data/raw"):
        """
        Initialize the crawler.
        
        Args:
            base_url: Root URL of the ED Data Express website
            output_dir: Directory to save downloaded files
        """
        self.base_url = base_url
        self.output_dir = output_dir
        self.visited_urls = set()
        self.url_queue = [base_url]
        self.domain = urlparse(base_url).netloc
        
        # Create output directories if they don't exist
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "html"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "js"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "css"), exist_ok=True)
        
        # Setup selenium for JavaScript-rendered content
        self.setup_selenium()
    
    def setup_selenium(self):
        """Set up Selenium WebDriver with multiple browser options."""
        options = None
        driver = None
        
        # Try browsers in order: Chrome, Firefox, Edge
        browsers = [
            self._setup_chrome,
            self._setup_firefox,
            self._setup_edge
        ]
        
        for setup_browser in browsers:
            try:
                driver = setup_browser()
                if driver:
                    self.driver = driver
                    logger.info(f"Successfully initialized {setup_browser.__name__.replace('_setup_', '')} driver")
                    return
            except Exception as e:
                logger.warning(f"Failed to initialize {setup_browser.__name__.replace('_setup_', '')}: {str(e)}")
        
        raise RuntimeError("Could not initialize any supported web driver")

    def _setup_chrome(self):
        """Set up Chrome WebDriver."""
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        try:
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except Exception as e:
            logger.warning(f"Chrome setup failed: {str(e)}")
            return None

    def _setup_firefox(self):
        """Set up Firefox WebDriver."""
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from webdriver_manager.firefox import GeckoDriverManager
        
        options = Options()
        options.add_argument("--headless")
        
        try:
            service = Service(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)
        except Exception as e:
            logger.warning(f"Firefox setup failed: {str(e)}")
            return None

    def _setup_edge(self):
        """Set up Edge WebDriver."""
        from selenium.webdriver.edge.options import Options
        from selenium.webdriver.edge.service import Service
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        try:
            service = Service(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)
        except Exception as e:
            logger.warning(f"Edge setup failed: {str(e)}")
            return None
    
    def url_to_filename(self, url):
        """Convert URL to a valid filename."""
        # Remove protocol and domain
        path = urlparse(url).path
        
        # Handle the root URL
        if path == "" or path == "/":
            return "index.html"
            
        # Remove leading/trailing slashes and replace remaining with underscore
        path = path.strip("/").replace("/", "_")
        
        # Add default extensions if missing
        if "." not in path:
            path += ".html"
            
        return path
    
    def download_file(self, url, file_type="html"):
        """
        Download a file from the given URL.
        
        Args:
            url: URL to download
            file_type: Type of file (html, js, css)
            
        Returns:
            Path to the saved file
        """
        try:
            # Use different approaches based on file type
            if file_type == "html":
                # Use Selenium for HTML to handle JavaScript rendering
                self.driver.get(url)
                time.sleep(2)  # Wait for JavaScript to execute
                content = self.driver.page_source
            else:
                # Use requests for other file types
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                content = response.text
            
            # Generate filename and path
            filename = self.url_to_filename(url)
            filepath = os.path.join(self.output_dir, file_type, filename)
            
            # Save the file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
                
            logger.info(f"Downloaded {url} to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error downloading {url}: {str(e)}")
            return None
    
    def extract_links(self, url, html_content):
        """
        Extract links from HTML content.
        
        Args:
            url: URL of the page being processed
            html_content: HTML content to parse
            
        Returns:
            List of discovered URLs to crawl
        """
        discovered_urls = []
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extract links from <a> tags
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            absolute_url = urljoin(url, href)
            
            # Only follow links within the same domain
            if urlparse(absolute_url).netloc == self.domain:
                discovered_urls.append({"url": absolute_url, "type": "html"})
        
        # Extract JavaScript files
        for script_tag in soup.find_all("script", src=True):
            src = script_tag["src"]
            absolute_url = urljoin(url, src)
            
            # Check if it's from the same domain
            if urlparse(absolute_url).netloc == self.domain:
                discovered_urls.append({"url": absolute_url, "type": "js"})
        
        # Extract CSS files
        for link_tag in soup.find_all("link", rel="stylesheet", href=True):
            href = link_tag["href"]
            absolute_url = urljoin(url, href)
            
            # Check if it's from the same domain
            if urlparse(absolute_url).netloc == self.domain:
                discovered_urls.append({"url": absolute_url, "type": "css"})
        
        return discovered_urls
    
    def crawl(self, max_pages=None):
        """
        Start the crawling process.
        
        Args:
            max_pages: Maximum number of pages to crawl (None for unlimited)
        """
        page_count = 0
        
        with tqdm(desc="Crawling pages", unit="page") as pbar:
            while self.url_queue and (max_pages is None or page_count < max_pages):
                # Get the next URL from the queue
                current_url = self.url_queue.pop(0)
                
                # Skip if already visited
                if current_url in self.visited_urls:
                    continue
                
                logger.info(f"Crawling: {current_url}")
                self.visited_urls.add(current_url)
                
                # Download the file
                file_type = "html"  # Default type
                if current_url.endswith(".js"):
                    file_type = "js"
                elif current_url.endswith(".css"):
                    file_type = "css"
                
                filepath = self.download_file(current_url, file_type)
                
                # If it's an HTML file, extract links from it
                if filepath and file_type == "html":
                    with open(filepath, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    
                    # Extract links and add them to the queue
                    discovered_links = self.extract_links(current_url, html_content)
                    for link in discovered_links:
                        if link["url"] not in self.visited_urls:
                            self.url_queue.append(link["url"])
                
                page_count += 1
                pbar.update(1)
                
                # Add a small delay to avoid overwhelming the server
                time.sleep(1)
        
        logger.info(f"Crawling completed. Processed {page_count} pages.")
    
    def close(self):
        """Clean up resources."""
        if hasattr(self, "driver"):
            self.driver.quit()


if __name__ == "__main__":
    crawler = EDDataExpressCrawler()
    try:
        crawler.crawl(max_pages=100)  # Limit to 100 pages for testing
    finally:
        crawler.close() 