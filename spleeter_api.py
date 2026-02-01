#!/usr/bin/env python3
"""
Spleeter API Service
A lightweight Flask API for audio source separation using Spleeter
"""

import os
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from spleeter.separator import Separator
import tempfile
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/app/uploads')
OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', '/app/outputs')
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'ogg', 'm4a', 'wma'}

# Initialize Spleeter separators (lazy loading)
separators = {}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_separator(model='spleeter:4stems'):
    """Get or create a Spleeter separator instance"""
    if model not in separators:
        logger.info(f"Initializing Spleeter model: {model}")
        separators[model] = Separator(model)
    return separators[model]


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'spleeter-api',
        'models_loaded': list(separators.keys())
    }), 200


@app.route('/models', methods=['GET'])
def list_models():
    """List available Spleeter models"""
    return jsonify({
        'models': [
            {
                'name': 'spleeter:2stems',
                'description': 'Vocals and accompaniment',
                'stems': ['vocals', 'accompaniment']
            },
            {
                'name': 'spleeter:4stems',
                'description': 'Vocals, drums, bass, other',
                'stems': ['vocals', 'drums', 'bass', 'other']
            },
            {
                'name': 'spleeter:5stems',
                'description': 'Vocals, drums, bass, piano, other',
                'stems': ['vocals', 'drums', 'bass', 'piano', 'other']
            }
        ]
    }), 200


@app.route('/separate', methods=['POST'])
def separate_audio():
    """
    Separate audio file into stems
    
    Form parameters:
    - file: Audio file (required)
    - model: Spleeter model (default: spleeter:4stems)
    - format: Output format - mp3 or wav (default: mp3)
    """
    
    # Check if file is present
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed: {ALLOWED_EXTENSIONS}'}), 400
    
    # Get parameters
    model = request.form.get('model', 'spleeter:4stems')
    output_format = request.form.get('format', 'mp3').lower()
    
    # Validate model
    valid_models = ['spleeter:2stems', 'spleeter:4stems', 'spleeter:5stems']
    if model not in valid_models:
        return jsonify({'error': f'Invalid model. Choose from: {valid_models}'}), 400
    
    # Validate format
    if output_format not in ['mp3', 'wav']:
        return jsonify({'error': 'Invalid format. Choose mp3 or wav'}), 400
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{filename}")
        file.save(input_path)
        
        logger.info(f"Processing file: {filename} with model: {model}")
        
        # Create output directory for this job
        job_output_dir = os.path.join(OUTPUT_FOLDER, job_id)
        os.makedirs(job_output_dir, exist_ok=True)
        
        # Get separator
        separator = get_separator(model)
        
        # Perform separation
        separator.separate_to_file(
            input_path,
            job_output_dir,
            codec=output_format,
            bitrate='320k' if output_format == 'mp3' else None
        )
        
        # Find the output directory (Spleeter creates a subdirectory with the input filename)
        base_name = Path(filename).stem
        stem_dir = os.path.join(job_output_dir, base_name)
        
        if not os.path.exists(stem_dir):
            raise Exception(f"Output directory not found: {stem_dir}")
        
        # List all generated stems
        stems = []
        for stem_file in os.listdir(stem_dir):
            if stem_file.endswith(f'.{output_format}'):
                stem_name = stem_file.replace(f'.{output_format}', '')
                stem_path = os.path.join(stem_dir, stem_file)
                
                stems.append({
                    'name': stem_name,
                    'filename': stem_file,
                    'path': stem_path,
                    'size': os.path.getsize(stem_path),
                    'download_url': f'/download/{job_id}/{stem_name}'
                })
        
        # Clean up input file
        os.remove(input_path)
        
        logger.info(f"Separation completed. Job ID: {job_id}, Stems: {len(stems)}")
        
        return jsonify({
            'status': 'success',
            'job_id': job_id,
            'model': model,
            'format': output_format,
            'stems': stems,
            'total_stems': len(stems)
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        
        # Clean up on error
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(job_output_dir):
            shutil.rmtree(job_output_dir)
        
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/download/<job_id>/<stem_name>', methods=['GET'])
def download_stem(job_id, stem_name):
    """Download a specific stem"""
    
    # Find the stem file
    job_output_dir = os.path.join(OUTPUT_FOLDER, job_id)
    
    if not os.path.exists(job_output_dir):
        return jsonify({'error': 'Job not found'}), 404
    
    # Search for the file in subdirectories
    for root, dirs, files in os.walk(job_output_dir):
        for file in files:
            if file.startswith(stem_name) and (file.endswith('.mp3') or file.endswith('.wav')):
                file_path = os.path.join(root, file)
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=file
                )
    
    return jsonify({'error': 'Stem not found'}), 404


@app.route('/cleanup/<job_id>', methods=['DELETE'])
def cleanup_job(job_id):
    """Clean up job files"""
    
    job_output_dir = os.path.join(OUTPUT_FOLDER, job_id)
    
    if not os.path.exists(job_output_dir):
        return jsonify({'error': 'Job not found'}), 404
    
    try:
        shutil.rmtree(job_output_dir)
        logger.info(f"Cleaned up job: {job_id}")
        return jsonify({
            'status': 'success',
            'message': f'Job {job_id} cleaned up'
        }), 200
    except Exception as e:
        logger.error(f"Error cleaning up job {job_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@app.route('/', methods=['GET'])
def index():
    """API information"""
    return jsonify({
        'service': 'Spleeter API',
        'version': '1.0.0',
        'endpoints': {
            'health': 'GET /health',
            'models': 'GET /models',
            'separate': 'POST /separate (multipart/form-data)',
            'download': 'GET /download/<job_id>/<stem_name>',
            'cleanup': 'DELETE /cleanup/<job_id>'
        },
        'documentation': 'https://github.com/deezer/spleeter'
    }), 200


if __name__ == '__main__':
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
