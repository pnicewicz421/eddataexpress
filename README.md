# ED Data Express Archive

A comprehensive solution to backup and preserve the ED Data Express website (https://eddataexpress.ed.gov/) and its underlying data for public access and historical preservation.

## Project Overview

This project aims to:
1. Archive the complete ED Data Express website including HTML, CSS, JS, and media files
2. Extract and preserve all underlying education data in accessible formats (CSV/Parquet)
3. Provide an interface for querying and visualizing the preserved data
4. Deploy the solution on AWS for public accessibility

## Project Structure

```
eddataexpress/
├── scraper/              # Web scraping modules
│   ├── site_crawler.py   # Main website crawler
│   ├── data_extractor.py # Data extraction utilities
│   └── media_downloader.py # Media file downloader
├── data/                 # Storage for extracted data
│   ├── raw/              # Raw downloaded files
│   ├── processed/        # Processed CSV/Parquet files
│   └── media/            # Downloaded media files
├── webapp/               # Web application for data querying/viewing
│   ├── app.py            # Main application file
│   ├── templates/        # HTML templates
│   └── static/           # Static assets
├── utils/                # Utility functions
├── tests/                # Test suite
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

## Setup and Usage

Instructions for setting up and running the project will be provided here.

## AWS Deployment

Details about deploying the solution on AWS will be added here.
