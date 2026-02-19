#!/usr/bin/env python3
"""
Video Upload Script
A simple Python script to upload video files to S3 via Lambda API Gateway.
Supports both direct and multipart uploads based on file size.
"""

import os
import sys
import json
import base64
import argparse
import requests
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import math


class UploadConfig:
    """Configuration for video uploads"""

    # File size limits
    MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
    CHUNK_SIZE = 5 * 1024 * 1024  # 5MB for multipart uploads
    DIRECT_UPLOAD_THRESHOLD = 100 * 1024 * 1024  # 100MB - use multipart above this

    # Allowed video formats
    ALLOWED_FORMATS = ['mp4', 'mov', 'avi', 'webm', 'mpeg', 'mkv']

    # Content type mapping
    CONTENT_TYPES = {
        'mp4': 'video/mp4',
        'mov': 'video/quicktime',
        'avi': 'video/x-msvideo',
        'webm': 'video/webm',
        'mpeg': 'video/mpeg',
        'mkv': 'video/x-matroska'
    }

    # API Configuration (override via environment variables)
    API_GATEWAY_URL = os.environ.get('API_GATEWAY_URL', 'https://your-api-gateway-url.amazonaws.com/prod')
    AUTH_TOKEN = os.environ.get('AUTH_TOKEN', '')

    # Endpoints
    ENDPOINT_VIDEO_UPLOAD = '/upload'
    ENDPOINT_MULTIPART_INIT = '/multipart/init'
    ENDPOINT_MULTIPART_COMPLETE = '/multipart/complete'


class UploadManager:
    """Main upload manager class"""

    def __init__(self, config: UploadConfig = None):
        self.config = config or UploadConfig()
        self.current_upload = None
        self.upload_history = []

    def validate_file(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """
        Validate the video file before upload

        Args:
            file_path: Path to the video file

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if file exists
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        if not file_path.is_file():
            return False, f"Not a file: {file_path}"

        # Check file size
        file_size = file_path.stat().st_size
        if file_size == 0:
            return False, "File is empty"

        if file_size > self.config.MAX_FILE_SIZE:
            return False, f"File size {self.format_file_size(file_size)} exceeds maximum {self.format_file_size(self.config.MAX_FILE_SIZE)}"

        # Check file format
        extension = file_path.suffix.lstrip('.').lower()
        if extension not in self.config.ALLOWED_FORMATS:
            return False, f"File format '{extension}' is not allowed. Allowed formats: {', '.join(self.config.ALLOWED_FORMATS)}"

        return True, None

    def get_content_type(self, file_path: Path) -> str:
        """Get content type for the file"""
        extension = file_path.suffix.lstrip('.').lower()
        return self.config.CONTENT_TYPES.get(extension, 'video/mp4')

    def upload_file(self, file_path: Path, verbose: bool = True) -> Dict:
        """
        Upload a video file

        Args:
            file_path: Path to the video file
            verbose: Whether to print progress information

        Returns:
            Upload result dictionary
        """
        # Validate file
        is_valid, error = self.validate_file(file_path)
        if not is_valid:
            raise ValueError(error)

        file_size = file_path.stat().st_size
        content_type = self.get_content_type(file_path)

        if verbose:
            print(f"📁 File: {file_path.name}")
            print(f"📊 Size: {self.format_file_size(file_size)}")
            print(f"🎬 Type: {content_type}")
            print()

        # Initialize upload info
        self.current_upload = {
            'file_path': file_path,
            'file_size': file_size,
            'content_type': content_type,
            'start_time': datetime.now(),
            'status': 'preparing',
            'progress': 0
        }

        # Determine upload method based on file size
        if file_size > self.config.DIRECT_UPLOAD_THRESHOLD:
            if verbose:
                print("🔄 Using multipart upload (large file)...")
            return self.start_multipart_upload(file_path, verbose)
        else:
            if verbose:
                print("⬆️  Using direct upload...")
            return self.start_direct_upload(file_path, verbose)

    def start_direct_upload(self, file_path: Path, verbose: bool = True) -> Dict:
        """
        Upload file directly using pre-signed URL

        Args:
            file_path: Path to the video file
            verbose: Whether to print progress

        Returns:
            Upload result dictionary
        """
        try:
            self.current_upload['status'] = 'initializing'

            # Call API to get pre-signed URL
            if verbose:
                print("🔑 Getting upload URL...")

            response = self.call_api(
                self.config.ENDPOINT_VIDEO_UPLOAD,
                {
                    'filename': file_path.name,
                    'fileSize': self.current_upload['file_size'],
                    'contentType': self.current_upload['content_type']
                }
            )

            upload_url = response.get('uploadUrl')
            file_key = response.get('fileKey')

            if not upload_url:
                raise Exception("No upload URL received from API")

            # Upload file to S3
            if verbose:
                print("📤 Uploading to S3...")

            self.current_upload['status'] = 'uploading'

            with open(file_path, 'rb') as f:
                file_data = f.read()

                upload_response = requests.put(
                    upload_url,
                    data=file_data,
                    headers={'Content-Type': self.current_upload['content_type']}
                )

                if upload_response.status_code not in [200, 201]:
                    raise Exception(f"S3 upload failed: {upload_response.status_code} - {upload_response.text}")

            self.current_upload['status'] = 'completed'
            self.current_upload['progress'] = 100

            elapsed = (datetime.now() - self.current_upload['start_time']).total_seconds()

            result = {
                'status': 'success',
                'message': 'Video uploaded successfully',
                'filename': file_path.name,
                'file_key': file_key,
                'file_size': self.current_upload['file_size'],
                'upload_type': 'direct',
                'elapsed_time': elapsed
            }

            if verbose:
                print("\n✅ Upload completed successfully!")
                print(f"⏱️  Time: {self.format_duration(elapsed)}")
                print(f"📍 File Key: {file_key}")

            # Add to history
            self.add_to_history(result)

            return result

        except Exception as e:
            self.current_upload['status'] = 'failed'
            error_msg = f"Direct upload failed: {str(e)}"
            if verbose:
                print(f"\n❌ {error_msg}")
            raise Exception(error_msg)

    def start_multipart_upload(self, file_path: Path, verbose: bool = True) -> Dict:
        """
        Upload large file using multipart upload

        Args:
            file_path: Path to the video file
            verbose: Whether to print progress

        Returns:
            Upload result dictionary
        """
        try:
            self.current_upload['status'] = 'initializing'

            # Initialize multipart upload
            if verbose:
                print("🔄 Initializing multipart upload...")

            response = self.call_api(
                self.config.ENDPOINT_MULTIPART_INIT,
                {
                    'filename': file_path.name,
                    'fileSize': self.current_upload['file_size'],
                    'contentType': self.current_upload['content_type']
                }
            )

            upload_id = response.get('uploadId')
            file_key = response.get('fileKey')
            parts = response.get('presignedUrls', [])
            part_size = response.get('partSize', self.config.CHUNK_SIZE)

            if not upload_id or not parts:
                raise Exception("Invalid multipart upload initialization response")

            self.current_upload['upload_id'] = upload_id
            self.current_upload['file_key'] = file_key
            self.current_upload['parts'] = parts

            # Upload parts
            if verbose:
                print(f"📦 Uploading {len(parts)} parts...")

            uploaded_parts = self.upload_parts(file_path, parts, part_size, verbose)

            # Complete multipart upload
            if verbose:
                print("🔗 Completing multipart upload...")

            result = self.complete_multipart_upload(upload_id, file_key, uploaded_parts, verbose)

            elapsed = (datetime.now() - self.current_upload['start_time']).total_seconds()
            result['elapsed_time'] = elapsed
            result['filename'] = file_path.name
            result['file_size'] = self.current_upload['file_size']

            if verbose:
                print("\n✅ Upload completed successfully!")
                print(f"⏱️  Time: {self.format_duration(elapsed)}")
                print(f"📍 File Key: {file_key}")

            # Add to history
            self.add_to_history(result)

            return result

        except Exception as e:
            self.current_upload['status'] = 'failed'
            error_msg = f"Multipart upload failed: {str(e)}"
            if verbose:
                print(f"\n❌ {error_msg}")
            raise Exception(error_msg)

    def upload_parts(self, file_path: Path, parts: List[Dict], part_size: int, verbose: bool = True) -> List[Dict]:
        """
        Upload all parts of a multipart upload

        Args:
            file_path: Path to the video file
            parts: List of part upload URLs
            verbose: Whether to print progress

        Returns:
            List of uploaded parts with ETags
        """
        uploaded_parts = []
        total_parts = len(parts)

        self.current_upload['status'] = 'uploading'

        with open(file_path, 'rb') as f:
            for i, part in enumerate(parts, 1):
                part_number = part['partNumber']
                upload_url = part['uploadUrl']

                # Read chunk
                start = (part_number - 1) * part_size
                f.seek(start)
                chunk = f.read(part_size)

                if verbose:
                    progress = (i / total_parts) * 100
                    print(f"  📤 Part {i}/{total_parts} ({progress:.1f}%)...", end='\r')

                # Upload chunk to S3
                response = requests.put(
                    upload_url,
                    data=chunk,
                    headers={'Content-Type': self.current_upload['content_type']}
                )

                if response.status_code not in [200, 201]:
                    raise Exception(f"Part {part_number} upload failed: {response.status_code}")

                etag = response.headers.get('ETag', '').strip('"')

                uploaded_parts.append({
                    'PartNumber': part_number,
                    'ETag': etag
                })

                # Update progress
                self.current_upload['progress'] = (i / total_parts) * 100

        if verbose:
            print(f"  ✓ All {total_parts} parts uploaded successfully" + " " * 20)

        return uploaded_parts

    def complete_multipart_upload(self, upload_id: str, file_key: str, parts: List[Dict], verbose: bool = True) -> Dict:
        """
        Complete the multipart upload

        Args:
            upload_id: Upload ID from initialization
            file_key: S3 file key
            parts: List of uploaded parts with ETags
            verbose: Whether to print progress

        Returns:
            Completion result dictionary
        """
        self.current_upload['status'] = 'completing'

        response = self.call_api(
            self.config.ENDPOINT_MULTIPART_COMPLETE,
            {
                'uploadId': upload_id,
                'fileKey': file_key,
                'parts': parts,
            }
        )

        self.current_upload['status'] = 'completed'
        self.current_upload['progress'] = 100

        return {
            'status': 'success',
            'message': 'Video uploaded successfully',
            'file_key': file_key,
            'upload_type': 'multipart'
        }

    def call_api(self, endpoint: str, data: Dict) -> Dict:
        """
        Make an API call to the Lambda endpoint

        Args:
            endpoint: API endpoint path
            data: Request payload

        Returns:
            API response dictionary
        """
        url = self.config.API_GATEWAY_URL.rstrip('/') + endpoint

        headers = {
            'Content-Type': 'application/json'
        }

        if self.config.AUTH_TOKEN:
            headers['Authorization'] = f"Bearer {self.config.AUTH_TOKEN}"

        response = requests.post(url, json=data, headers=headers)

        if response.status_code not in [200, 201]:
            error_data = {}
            try:
                error_data = response.json()
            except:
                pass

            error_msg = error_data.get('message', response.text) or f"API call failed: {response.status_code}"
            raise Exception(error_msg)

        return response.json()

    def add_to_history(self, upload_info: Dict):
        """Add upload to history"""
        upload_info['timestamp'] = datetime.now().isoformat()
        self.upload_history.append(upload_info)

    @staticmethod
    def format_file_size(bytes_size: int) -> str:
        """Format file size in human-readable format"""
        if bytes_size == 0:
            return '0 B'

        units = ['B', 'KB', 'MB', 'GB', 'TB']
        k = 1024
        i = math.floor(math.log(bytes_size) / math.log(k))

        size = bytes_size / math.pow(k, i)
        return f"{size:.2f} {units[i]}"

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"


def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(
        description='Upload video files to S3 via Lambda API Gateway',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Upload a video file
  python upload_video.py /path/to/video.mp4
  
  # Upload with custom API Gateway URL
  API_GATEWAY_URL=https://your-api.amazonaws.com/prod python upload_video.py video.mp4
  
  # Upload with authentication token
  AUTH_TOKEN=your-token python upload_video.py video.mp4
  
  # Quiet mode (no progress output)
  python upload_video.py video.mp4 --quiet

Environment Variables:
  API_GATEWAY_URL    API Gateway endpoint URL
  AUTH_TOKEN         Authentication token (if required)
        '''
    )

    parser.add_argument(
        'file_path',
        type=str,
        help='Path to the video file to upload'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress progress output'
    )

    parser.add_argument(
        '--api-url',
        type=str,
        help='API Gateway URL (overrides API_GATEWAY_URL env var)'
    )

    parser.add_argument(
        '--token',
        type=str,
        help='Authentication token (overrides AUTH_TOKEN env var)'
    )

    args = parser.parse_args()

    # Configure
    config = UploadConfig()
    if args.api_url:
        config.API_GATEWAY_URL = args.api_url
    if args.token:
        config.AUTH_TOKEN = args.token

    # Validate configuration
    if not config.API_GATEWAY_URL or config.API_GATEWAY_URL == 'https://your-api-gateway-url.amazonaws.com/prod':
        print("❌ Error: API_GATEWAY_URL not configured")
        print("Set the API_GATEWAY_URL environment variable or use --api-url")
        sys.exit(1)

    # Create upload manager
    manager = UploadManager(config)

    # Upload file
    try:
        file_path = Path(args.file_path).resolve()

        if not args.quiet:
            print("=" * 60)
            print("🎬 Video Upload Script")
            print("=" * 60)
            print()

        result = manager.upload_file(file_path, verbose=not args.quiet)

        if not args.quiet:
            print()
            print("=" * 60)

        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Upload cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

