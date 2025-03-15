"""
ED Data Express Archive Web Application

A Flask web application that provides a user interface for:
1. Browsing the archived website
2. Querying and visualizing the extracted data
3. Accessing downloaded media files
"""

import os
import glob
import json
import pandas as pd
import pyarrow.parquet as pq
from flask import Flask, render_template, request, jsonify, send_from_directory, abort

app = Flask(__name__)

# Configuration
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
MEDIA_DIR = os.path.join(DATA_DIR, "media")

@app.route('/')
def index():
    """Render the homepage."""
    # Count available resources
    html_count = len(glob.glob(os.path.join(RAW_DIR, "html", "*.html")))
    csv_count = len(glob.glob(os.path.join(PROCESSED_DIR, "csv", "*.csv")))
    parquet_count = len(glob.glob(os.path.join(PROCESSED_DIR, "parquet", "*.parquet")))
    image_count = len(glob.glob(os.path.join(MEDIA_DIR, "images", "*")))
    
    return render_template(
        'index.html',
        html_count=html_count,
        csv_count=csv_count,
        parquet_count=parquet_count,
        image_count=image_count
    )

@app.route('/browse')
def browse():
    """Browse the archived website files."""
    page = request.args.get('page', 'index.html')
    
    # Security check - prevent directory traversal
    if '..' in page or page.startswith('/'):
        abort(403)
    
    # Path to the HTML file
    file_path = os.path.join(RAW_DIR, "html", page)
    
    if not os.path.exists(file_path):
        abort(404)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Get a list of all HTML files for navigation
    html_files = [
        os.path.basename(f) for f in 
        glob.glob(os.path.join(RAW_DIR, "html", "*.html"))
    ]
    
    return render_template(
        'browse.html',
        page=page,
        content=content,
        html_files=sorted(html_files)
    )

@app.route('/data')
def data_explorer():
    """Data explorer page."""
    # Get list of available datasets (CSV files)
    datasets = [
        os.path.basename(f).replace('.csv', '') 
        for f in glob.glob(os.path.join(PROCESSED_DIR, "csv", "*.csv"))
    ]
    
    return render_template('data.html', datasets=sorted(datasets))

@app.route('/api/datasets')
def api_datasets():
    """API endpoint to list available datasets."""
    datasets = []
    
    # Get all CSV files
    csv_files = glob.glob(os.path.join(PROCESSED_DIR, "csv", "*.csv"))
    
    for csv_file in csv_files:
        name = os.path.basename(csv_file).replace('.csv', '')
        
        # Try to get metadata if available
        metadata_file = os.path.join(PROCESSED_DIR, "json", f"{name}_metadata.json")
        metadata = {}
        
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except:
                pass
        
        # Get column names and row count
        try:
            df = pd.read_csv(csv_file, nrows=1)
            columns = df.columns.tolist()
            
            # Count rows efficiently
            row_count = sum(1 for _ in open(csv_file, 'r', encoding='utf-8')) - 1
            
            datasets.append({
                'name': name,
                'columns': columns,
                'row_count': row_count,
                'metadata': metadata
            })
        except:
            # If we can't read the file, still include basic info
            datasets.append({
                'name': name,
                'error': 'Could not read file',
                'metadata': metadata
            })
    
    return jsonify(datasets)

@app.route('/api/data/<dataset>')
def api_dataset(dataset):
    """API endpoint to get data from a specific dataset."""
    # Security check
    if '..' in dataset or '/' in dataset:
        abort(403)
    
    csv_file = os.path.join(PROCESSED_DIR, "csv", f"{dataset}.csv")
    
    if not os.path.exists(csv_file):
        abort(404)
    
    # Parse query parameters
    limit = request.args.get('limit', '100')
    offset = request.args.get('offset', '0')
    
    try:
        limit = int(limit)
        offset = int(offset)
    except:
        limit = 100
        offset = 0
    
    # Cap limit to reasonable value
    if limit > 1000:
        limit = 1000
    
    # Get sorting parameters
    sort_by = request.args.get('sort_by', None)
    sort_dir = request.args.get('sort_dir', 'asc')
    
    # Read the data
    try:
        df = pd.read_csv(csv_file)
        
        # Apply filters if specified
        for column in df.columns:
            filter_value = request.args.get(f'filter_{column}', None)
            if filter_value:
                df = df[df[column].astype(str).str.contains(filter_value, case=False)]
        
        # Apply sorting
        if sort_by and sort_by in df.columns:
            df = df.sort_values(by=sort_by, ascending=(sort_dir.lower() == 'asc'))
        
        # Get total count after filtering
        total_count = len(df)
        
        # Apply pagination
        df = df.iloc[offset:offset+limit]
        
        # Convert to dict for JSON response
        records = df.to_dict(orient='records')
        
        return jsonify({
            'data': records,
            'total': total_count,
            'offset': offset,
            'limit': limit
        })
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/media')
def media_browser():
    """Media files browser."""
    media_type = request.args.get('type', 'images')
    
    # Security check
    if media_type not in ['images', 'videos', 'documents', 'other']:
        abort(403)
    
    # Get list of media files
    files = [
        os.path.basename(f) 
        for f in glob.glob(os.path.join(MEDIA_DIR, media_type, "*"))
    ]
    
    return render_template(
        'media.html',
        media_type=media_type,
        files=sorted(files)
    )

@app.route('/media/<media_type>/<filename>')
def serve_media(media_type, filename):
    """Serve media files."""
    # Security check
    if media_type not in ['images', 'videos', 'documents', 'other']:
        abort(403)
    
    if '..' in filename or '/' in filename:
        abort(403)
    
    return send_from_directory(
        os.path.join(MEDIA_DIR, media_type),
        filename
    )

@app.route('/assets/<path:path>')
def serve_assets(path):
    """Serve static assets from the raw directory."""
    # Security check
    if '..' in path:
        abort(403)
    
    # Check if it's a JS or CSS file
    if path.endswith('.js'):
        return send_from_directory(os.path.join(RAW_DIR, "js"), path)
    elif path.endswith('.css'):
        return send_from_directory(os.path.join(RAW_DIR, "css"), path)
    else:
        abort(404)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 