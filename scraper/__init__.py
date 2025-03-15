"""
ED Data Express Scraper

A comprehensive scraper for https://eddataexpress.ed.gov/ that archives the website,
extracts underlying data, and downloads media files.
"""

from .site_crawler import EDDataExpressCrawler
from .data_extractor import EDDataExtractor
from .media_downloader import MediaDownloader

__version__ = "0.1.0" 