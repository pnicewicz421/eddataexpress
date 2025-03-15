"""
Data Extractor for ED Data Express

This module handles extracting structured data from the ED Data Express website
and saving it in usable formats (CSV, Parquet).
"""

import os
import re
import json
import logging
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from bs4 import BeautifulSoup
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse, parse_qs, urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data_extractor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("data_extractor")

class EDDataExtractor:
    """Data extractor for ED Data Express website."""
    
    def __init__(self, base_url="https://eddataexpress.ed.gov/", output_dir="data/processed"):
        """
        Initialize the data extractor.
        
        Args:
            base_url: Root URL of the ED Data Express website
            output_dir: Directory to save processed data files
        """
        self.base_url = base_url
        self.output_dir = output_dir
        self.domain = urlparse(base_url).netloc
        
        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "csv"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "parquet"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "json"), exist_ok=True)
        
        # Setup selenium for JavaScript-rendered content
        self.setup_selenium()
    
    def setup_selenium(self):
        """Set up Selenium WebDriver for JavaScript-rendered content."""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
    
    def close(self):
        """Clean up resources."""
        if hasattr(self, "driver"):
            self.driver.quit()
    
    def extract_data_from_html(self, html_file):
        """
        Extract data tables from an HTML file.
        
        Args:
            html_file: Path to the HTML file to extract data from
            
        Returns:
            List of DataFrames found in the HTML
        """
        try:
            tables = []
            
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Try to extract tables with pandas
            table_list = pd.read_html(content)
            
            if table_list:
                logger.info(f"Found {len(table_list)} tables in {html_file} using pandas")
                tables.extend(table_list)
            
            return tables
            
        except Exception as e:
            logger.error(f"Error extracting data from {html_file}: {str(e)}")
            return []
    
    def extract_data_from_website(self, url, data_selector=None):
        """
        Extract data directly from a website URL using Selenium.
        
        Args:
            url: URL to extract data from
            data_selector: CSS selector to find data tables (optional)
            
        Returns:
            List of DataFrames found on the page
        """
        try:
            tables = []
            
            # Load the page
            logger.info(f"Extracting data from URL: {url}")
            self.driver.get(url)
            
            # Wait for page to load (adjust timeout as needed)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # If specific selector provided, wait for it
            if data_selector:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, data_selector))
                )
            
            # Try to extract tables with pandas
            html = self.driver.page_source
            try:
                table_list = pd.read_html(html)
                if table_list:
                    logger.info(f"Found {len(table_list)} tables in {url} using pandas")
                    tables.extend(table_list)
            except Exception as e:
                logger.warning(f"Pandas couldn't extract tables from {url}: {str(e)}")
            
            # If no tables found or specific selector provided, try extracting manually
            if not tables and data_selector:
                elements = self.driver.find_elements(By.CSS_SELECTOR, data_selector)
                for i, element in enumerate(elements):
                    try:
                        # Get HTML of the element and try to parse as table
                        element_html = element.get_attribute("outerHTML")
                        element_tables = pd.read_html(element_html)
                        if element_tables:
                            tables.extend(element_tables)
                    except Exception as e:
                        logger.warning(f"Failed to extract table from element {i}: {str(e)}")
            
            return tables
            
        except Exception as e:
            logger.error(f"Error extracting data from {url}: {str(e)}")
            return []
    
    def extract_api_data(self, url):
        """
        Extract data from API endpoints.
        
        Args:
            url: API URL to extract data from
            
        Returns:
            DataFrame containing the API response data
        """
        try:
            logger.info(f"Extracting API data from: {url}")
            
            # Load the page with Selenium (in case it's not a direct API)
            self.driver.get(url)
            
            # Check if we got a JSON response
            try:
                pre_elements = self.driver.find_elements(By.TAG_NAME, "pre")
                if pre_elements:
                    # Try parsing the content of each pre tag as JSON
                    for pre in pre_elements:
                        try:
                            content = pre.text
                            data = json.loads(content)
                            
                            # Convert to DataFrame if possible
                            if isinstance(data, list):
                                return pd.DataFrame(data)
                            elif isinstance(data, dict):
                                # Try a few common JSON API patterns
                                if "results" in data:
                                    return pd.DataFrame(data["results"])
                                elif "data" in data:
                                    return pd.DataFrame(data["data"])
                                elif "items" in data:
                                    return pd.DataFrame(data["items"])
                                else:
                                    # Handle flat JSON
                                    return pd.DataFrame([data])
                        except:
                            continue
            except:
                pass
            
            # Get page source and check if it looks like JSON
            content = self.driver.page_source
            
            # Remove HTML tags for a cleaner check
            soup = BeautifulSoup(content, "html.parser")
            text_content = soup.get_text()
            
            # Try to parse as JSON
            try:
                data = json.loads(text_content)
                
                # Convert to DataFrame if possible
                if isinstance(data, list):
                    return pd.DataFrame(data)
                elif isinstance(data, dict):
                    # Try a few common JSON API patterns
                    if "results" in data:
                        return pd.DataFrame(data["results"])
                    elif "data" in data:
                        return pd.DataFrame(data["data"])
                    elif "items" in data:
                        return pd.DataFrame(data["items"])
                    else:
                        # Handle flat JSON
                        return pd.DataFrame([data])
            except:
                pass
            
            # If we couldn't get JSON, return None
            logger.warning(f"Could not extract JSON data from {url}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting API data from {url}: {str(e)}")
            return None
    
    def save_dataframe(self, df, name, metadata=None):
        """
        Save a DataFrame to CSV and Parquet formats.
        
        Args:
            df: DataFrame to save
            name: Base name for the saved files (without extension)
            metadata: Optional metadata dictionary to attach to the Parquet file
        """
        if df is None or df.empty:
            logger.warning(f"Skipping empty DataFrame: {name}")
            return
        
        try:
            # Clean the name to use as a filename
            clean_name = re.sub(r'[^\w\-_]', '_', name)
            
            # Save as CSV
            csv_path = os.path.join(self.output_dir, "csv", f"{clean_name}.csv")
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved CSV: {csv_path}")
            
            # Save as Parquet
            parquet_path = os.path.join(self.output_dir, "parquet", f"{clean_name}.parquet")
            table = pa.Table.from_pandas(df)
            
            # Add metadata if provided
            if metadata:
                # Convert metadata values to strings for Parquet compatibility
                str_metadata = {k: str(v) for k, v in metadata.items()}
                table = table.replace_schema_metadata({
                    **table.schema.metadata,
                    **str_metadata
                })
            
            pq.write_table(table, parquet_path)
            logger.info(f"Saved Parquet: {parquet_path}")
            
            # Save metadata as JSON
            if metadata:
                json_path = os.path.join(self.output_dir, "json", f"{clean_name}_metadata.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)
                logger.info(f"Saved metadata: {json_path}")
                
        except Exception as e:
            logger.error(f"Error saving DataFrame {name}: {str(e)}")
    
    def process_data_page(self, url, name=None, data_selector=None):
        """
        Process a data page to extract and save data.
        
        Args:
            url: URL of the data page
            name: Base name for the saved files (without extension)
            data_selector: CSS selector to find data tables (optional)
        """
        try:
            # Generate name from URL if not provided
            if not name:
                path = urlparse(url).path
                name = os.path.basename(path) or "index"
                
                # Remove file extension if present
                name = os.path.splitext(name)[0]
            
            # Extract data from website
            tables = self.extract_data_from_website(url, data_selector)
            
            # Save each table
            for i, df in enumerate(tables):
                table_name = f"{name}_table_{i+1}" if len(tables) > 1 else name
                
                # Create metadata
                metadata = {
                    "source_url": url,
                    "table_index": i,
                    "extractor": "EDDataExtractor",
                    "selector": data_selector
                }
                
                self.save_dataframe(df, table_name, metadata)
            
            # If no tables found, try API extraction
            if not tables:
                df = self.extract_api_data(url)
                if df is not None:
                    self.save_dataframe(df, f"{name}_api", {"source_url": url})
                
        except Exception as e:
            logger.error(f"Error processing data page {url}: {str(e)}")
    
    def discover_data_urls(self):
        """
        Discover data URLs on the ED Data Express website.
        
        Returns:
            List of URLs likely to contain data
        """
        data_urls = []
        
        # Common data URL patterns for ED Data Express
        data_patterns = [
            "/data/",
            "data-files",
            "download",
            "report",
            "table",
            "csv",
            "excel",
            ".xlsx",
            ".csv",
            "api",
            "json"
        ]
        
        # Start with the homepage
        self.driver.get(self.base_url)
        
        # Find all links and check if they match data patterns
        links = self.driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and urlparse(href).netloc == self.domain:
                    # Check if the URL matches any data pattern
                    if any(pattern in href.lower() for pattern in data_patterns):
                        data_urls.append(href)
                        logger.info(f"Found data URL: {href}")
            except:
                continue
        
        # Also check for URLs with "state-tables" or similar
        try:
            self.driver.get(urljoin(self.base_url, "state-tables"))
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if href and urlparse(href).netloc == self.domain:
                        data_urls.append(href)
                except:
                    continue
        except:
            logger.warning("Could not access state-tables page")
        
        return list(set(data_urls))  # Remove duplicates
    
    def extract_all_data(self, data_urls=None):
        """
        Extract and save data from all discovered data URLs.
        
        Args:
            data_urls: List of URLs to extract data from (if None, will discover them)
        """
        if data_urls is None:
            logger.info("Discovering data URLs...")
            data_urls = self.discover_data_urls()
        
        logger.info(f"Found {len(data_urls)} data URLs to process")
        
        # Process each data URL
        for url in tqdm(data_urls, desc="Processing data URLs"):
            self.process_data_page(url)


if __name__ == "__main__":
    # Example usage
    extractor = EDDataExtractor()
    try:
        extractor.extract_all_data()
    finally:
        extractor.close() 