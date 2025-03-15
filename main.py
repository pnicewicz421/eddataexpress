#!/usr/bin/env python3
"""
ED Data Express Archive Tool

This script orchestrates the complete archiving process for ED Data Express:
1. Crawl and save the website HTML, CSS, and JavaScript
2. Extract and save structured data (CSV, Parquet)
3. Download and organize media files (images, videos, documents)

Usage:
    python main.py [--max-pages=N] [--skip-media] [--skip-data] [--only-html]

Options:
    --max-pages=N    Limit the number of pages to crawl (default: no limit)
    --skip-media     Skip downloading media files
    --skip-data      Skip extracting data
    --only-html      Only crawl and save HTML/CSS/JS files
"""

import os
import sys
import time
import logging
import argparse
from scraper.site_crawler import EDDataExpressCrawler
from scraper.data_extractor import EDDataExtractor
from scraper.media_downloader import MediaDownloader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("archive.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("main")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="ED Data Express Archive Tool")
    
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit the number of pages to crawl (default: no limit)"
    )
    
    parser.add_argument(
        "--skip-media",
        action="store_true",
        help="Skip downloading media files"
    )
    
    parser.add_argument(
        "--skip-data",
        action="store_true",
        help="Skip extracting data"
    )
    
    parser.add_argument(
        "--only-html",
        action="store_true",
        help="Only crawl and save HTML/CSS/JS files"
    )
    
    return parser.parse_args()

def main():
    """Main execution function."""
    args = parse_arguments()
    
    # Create base directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    start_time = time.time()
    logger.info("Starting ED Data Express archive process")
    
    # Step 1: Crawl the website
    logger.info("Step 1: Crawling the website")
    crawler = EDDataExpressCrawler(
        base_url="https://eddataexpress.ed.gov/",
        output_dir="data/raw"
    )
    
    try:
        crawler.crawl(max_pages=args.max_pages)
    except Exception as e:
        logger.error(f"Error during website crawling: {str(e)}")
    finally:
        crawler.close()
    
    # If only HTML is requested, stop here
    if args.only_html:
        elapsed_time = time.time() - start_time
        logger.info(f"Archive process completed in {elapsed_time:.2f} seconds")
        return
    
    # Step 2: Extract data (unless skipped)
    if not args.skip_data:
        logger.info("Step 2: Extracting data")
        extractor = EDDataExtractor(
            base_url="https://eddataexpress.ed.gov/",
            output_dir="data/processed"
        )
        
        try:
            extractor.extract_all_data()
        except Exception as e:
            logger.error(f"Error during data extraction: {str(e)}")
        finally:
            extractor.close()
    
    # Step 3: Download media files (unless skipped)
    if not args.skip_media:
        logger.info("Step 3: Downloading media files")
        media_downloader = MediaDownloader(
            base_url="https://eddataexpress.ed.gov/",
            output_dir="data/media"
        )
        
        try:
            media_downloader.process_html_directory(
                html_dir="data/raw/html",
                base_url="https://eddataexpress.ed.gov/"
            )
        except Exception as e:
            logger.error(f"Error during media download: {str(e)}")
    
    # Completed
    elapsed_time = time.time() - start_time
    logger.info(f"Archive process completed in {elapsed_time:.2f} seconds")
    
    # Summary
    if os.path.exists("data/raw/html"):
        html_count = len([f for f in os.listdir("data/raw/html") if f.endswith(".html")])
        logger.info(f"HTML files archived: {html_count}")
    
    if os.path.exists("data/processed/csv"):
        csv_count = len([f for f in os.listdir("data/processed/csv") if f.endswith(".csv")])
        logger.info(f"CSV data files extracted: {csv_count}")
    
    if os.path.exists("data/media/images"):
        image_count = len(os.listdir("data/media/images"))
        logger.info(f"Images downloaded: {image_count}")

if __name__ == "__main__":
    main() 