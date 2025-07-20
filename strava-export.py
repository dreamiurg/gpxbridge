#!/usr/bin/env python3
"""
Strava GPX Export Tool

This script exports recent activities from your Strava account as GPX files.
Since Strava API doesn't provide direct GPX export for activities, this tool
uses activity streams to reconstruct the GPX data.

Setup:
1. Create a Strava API application at https://www.strava.com/settings/api
2. Set environment variables or pass credentials via command line
3. Install required packages: pip install requests gpxpy click

Environment Variables:
- STRAVA_CLIENT_ID: Your Strava app client ID
- STRAVA_CLIENT_SECRET: Your Strava app client secret  
- STRAVA_REFRESH_TOKEN: Your refresh token

Usage:
python strava-export.py --count 10 --output-dir gpx_exports
python strava-export.py --client-id ID --client-secret SECRET --refresh-token TOKEN
"""

import requests
import json
import os
import click
from datetime import datetime
from typing import List, Dict, Optional
import gpxpy
import gpxpy.gpx
import time
import random

class StravaExporter:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, delay: float = 1.0):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.base_url = "https://www.strava.com/api/v3"
        self.delay = delay  # Delay between requests in seconds
        self.rate_limit_info = {"15min_usage": 0, "15min_limit": 100, "daily_usage": 0, "daily_limit": 1000}
        
    def get_access_token(self) -> bool:
        """Exchange refresh token for access token"""
        try:
            response = requests.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            click.echo("✓ Successfully obtained access token")
            return True
        except requests.exceptions.RequestException as e:
            click.echo(f"✗ Failed to get access token: {e}", err=True)
            return False
    
    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests"""
        return {"Authorization": f"Bearer {self.access_token}"}
    
    def update_rate_limit_info(self, response: requests.Response):
        """Update rate limit tracking from response headers"""
        usage_header = response.headers.get('X-RateLimit-Usage')
        limit_header = response.headers.get('X-RateLimit-Limit')
        
        if usage_header:
            # Format: "15min_usage,daily_usage"
            parts = usage_header.split(',')
            if len(parts) >= 2:
                self.rate_limit_info["15min_usage"] = int(parts[0])
                self.rate_limit_info["daily_usage"] = int(parts[1])
        
        if limit_header:
            # Format: "15min_limit,daily_limit" 
            parts = limit_header.split(',')
            if len(parts) >= 2:
                self.rate_limit_info["15min_limit"] = int(parts[0])
                self.rate_limit_info["daily_limit"] = int(parts[1])
    
    def check_rate_limit(self):
        """Check if we're approaching rate limits and warn user"""
        fifteen_min_pct = (self.rate_limit_info["15min_usage"] / self.rate_limit_info["15min_limit"]) * 100
        daily_pct = (self.rate_limit_info["daily_usage"] / self.rate_limit_info["daily_limit"]) * 100
        
        if fifteen_min_pct > 80:
            click.echo(f"⚠ Warning: Using {fifteen_min_pct:.1f}% of 15-minute rate limit")
        if daily_pct > 80:
            click.echo(f"⚠ Warning: Using {daily_pct:.1f}% of daily rate limit")
    
    def handle_rate_limit_error(self, attempt: int, max_retries: int = 3) -> bool:
        """Handle 429 rate limit errors with exponential backoff"""
        if attempt >= max_retries:
            click.echo(f"✗ Max retries ({max_retries}) reached for rate limit", err=True)
            return False
        
        # Exponential backoff: 15min + jitter for first retry, then 30min, 60min
        base_delay = 15 * 60 * (2 ** attempt)  # 15min, 30min, 60min
        jitter = random.uniform(0, 60)  # Add up to 1 minute jitter
        total_delay = base_delay + jitter
        
        minutes = total_delay / 60
        click.echo(f"⏳ Rate limit hit. Waiting {minutes:.1f} minutes before retry {attempt + 1}/{max_retries}...")
        time.sleep(total_delay)
        return True
    
    def make_api_request(self, url: str, params: Dict = None, max_retries: int = 3) -> Optional[requests.Response]:
        """Make API request with rate limiting and retry logic"""
        for attempt in range(max_retries + 1):
            try:
                # Add delay between requests (except first request)
                if attempt > 0 or hasattr(self, '_request_count'):
                    time.sleep(self.delay)
                
                response = requests.get(url, headers=self.get_headers(), params=params or {})
                
                # Update rate limit tracking
                self.update_rate_limit_info(response)
                
                # Track request count for delay logic
                self._request_count = getattr(self, '_request_count', 0) + 1
                
                if response.status_code == 429:
                    # Rate limit hit
                    if not self.handle_rate_limit_error(attempt, max_retries):
                        return None
                    continue
                
                response.raise_for_status()
                
                # Check if we're approaching limits
                self.check_rate_limit()
                
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries and "429" in str(e):
                    continue
                click.echo(f"✗ API request failed: {e}", err=True)
                return None
        
        return None
    
    def get_recent_activities(self, count: int = 30) -> List[Dict]:
        """Fetch recent activities from Strava with pagination support"""
        activities = []
        page = 1
        per_page = 200  # Strava API max is 200 per page
        
        click.echo(f"Fetching {count} activities with pagination (max {per_page} per request)...")
        
        while len(activities) < count:
            try:
                remaining = count - len(activities)
                current_per_page = min(per_page, remaining)
                
                click.echo(f"  Requesting page {page} with {current_per_page} activities...")
                
                response = self.make_api_request(
                    f"{self.base_url}/athlete/activities",
                    params={"per_page": current_per_page, "page": page}
                )
                if not response:
                    return activities
                page_activities = response.json()
                
                if not page_activities:
                    # No more activities available
                    click.echo(f"  No more activities available on page {page}")
                    break
                    
                activities.extend(page_activities)
                click.echo(f"  Retrieved {len(page_activities)} activities (total: {len(activities)})")
                
                if len(page_activities) < current_per_page:
                    # Fewer activities returned than requested, we've reached the end
                    click.echo(f"  Reached end of activities (got {len(page_activities)}, expected {current_per_page})")
                    break
                    
                page += 1
                
            except requests.exceptions.RequestException as e:
                click.echo(f"✗ Failed to fetch activities: {e}", err=True)
                return activities
        
        # Trim to exact count requested
        activities = activities[:count]
        click.echo(f"✓ Found {len(activities)} recent activities")
        return activities
    
    def get_activity_streams(self, activity_id: int) -> Optional[Dict]:
        """Get activity stream data (coordinates, time, etc.)"""
        response = self.make_api_request(
            f"{self.base_url}/activities/{activity_id}/streams",
            params={
                "keys": "latlng,time,altitude,distance,heartrate,cadence,watts",
                "key_by_type": "true"
            }
        )
        if not response:
            return None
        return response.json()
    
    def create_gpx_from_streams(self, activity: Dict, streams: Dict) -> Optional[gpxpy.gpx.GPX]:
        """Convert Strava activity streams to GPX format"""
        if not streams or "latlng" not in streams:
            click.echo(f"  ⚠ No GPS data available for activity {activity['id']}")
            return None
            
        gpx = gpxpy.gpx.GPX()
        
        # Set GPX metadata from Strava activity
        gpx.name = activity.get("name", f"Activity {activity['id']}")
        gpx.description = f"https://www.strava.com/activities/{activity['id']}"
        
        # Set creation time to activity start time
        start_time = datetime.fromisoformat(activity["start_date_local"].replace("Z", "+00:00"))
        gpx.time = start_time
        
        # Create track
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_track.name = activity.get("name", f"Activity {activity['id']}")
        gpx.tracks.append(gpx_track)
        
        # Create track segment
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        
        # Get data streams
        latlng_data = streams["latlng"]["data"]
        time_data = streams.get("time", {}).get("data", [])
        altitude_data = streams.get("altitude", {}).get("data", [])
        heartrate_data = streams.get("heartrate", {}).get("data", [])
        
        # Parse start time
        start_time = datetime.fromisoformat(activity["start_date_local"].replace("Z", "+00:00"))
        
        # Create track points
        for i, (lat, lng) in enumerate(latlng_data):
            point = gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lng)
            
            # Add timestamp
            if i < len(time_data):
                from datetime import timedelta
                point.time = start_time + timedelta(seconds=time_data[i])
            
            # Add elevation
            if i < len(altitude_data):
                point.elevation = altitude_data[i]
                
            # Add heart rate as extension
            if i < len(heartrate_data):
                # Note: GPX heart rate extensions require additional XML handling
                # For simplicity, we'll skip this in the basic implementation
                pass
                
            gpx_segment.points.append(point)
        
        return gpx
    
    def export_activity_to_gpx(self, activity: Dict, output_dir: str = "gpx_exports", organize_by_type: bool = False) -> bool:
        """Export a single activity to GPX file"""
        activity_id = activity["id"]
        activity_name = activity.get("name", f"Activity {activity_id}")
        activity_type = activity.get("type", "Unknown")
        start_date = datetime.fromisoformat(activity["start_date_local"].replace("Z", "+00:00"))
        
        click.echo(f"  Processing: {start_date.strftime('%Y-%m-%d')} | {activity_type} | {activity_name}")
        
        # Get activity streams
        streams = self.get_activity_streams(activity_id)
        if not streams:
            return False
        
        # Create GPX from streams
        gpx = self.create_gpx_from_streams(activity, streams)
        if not gpx:
            return False
        
        # Determine final output directory
        if organize_by_type:
            # Create subdirectory for activity type
            safe_type_dir = "".join(c for c in activity_type.lower() if c.isalnum() or c in ('-', '_'))
            final_output_dir = os.path.join(output_dir, safe_type_dir)
        else:
            final_output_dir = output_dir
        
        # Create output directory
        os.makedirs(final_output_dir, exist_ok=True)
        
        # Generate filename
        safe_name = "".join(c for c in activity_name if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
        safe_name = safe_name.replace(' ', '-')
        safe_type = "".join(c for c in activity_type if c.isalnum() or c in ('-', '_'))
        filename = f"{start_date.strftime('%Y%m%d')}_{safe_type}_{safe_name}_{activity_id}.gpx"
        filepath = os.path.join(final_output_dir, filename)
        
        # Write GPX file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(gpx.to_xml())
            click.echo(f"  ✓ Saved: {filepath}")
            return True
        except Exception as e:
            click.echo(f"  ✗ Failed to save {filepath}: {e}", err=True)
            return False
    
    def load_progress(self, progress_file: str) -> Dict:
        """Load progress from file to resume interrupted exports"""
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"exported_activities": [], "last_activity_index": 0}
    
    def save_progress(self, progress_file: str, progress: Dict):
        """Save export progress to file"""
        try:
            with open(progress_file, 'w') as f:
                json.dump(progress, f, indent=2)
        except Exception as e:
            click.echo(f"⚠ Failed to save progress: {e}", err=True)
    
    def export_recent_activities(self, count: int = 10, output_dir: str = "gpx_exports", organize_by_type: bool = False, resume: bool = False):
        """Export recent activities to GPX files with progress tracking"""
        if not self.get_access_token():
            return
        
        # Progress tracking
        progress_file = os.path.join(output_dir, ".strava_export_progress.json")
        progress = {"exported_activities": [], "last_activity_index": 0}
        
        if resume:
            progress = self.load_progress(progress_file)
            if progress["exported_activities"]:
                click.echo(f"📄 Resuming export from activity {progress['last_activity_index'] + 1}")
        
        click.echo(f"Fetching {count} recent activities...")
        activities = self.get_recent_activities(count)
        
        if not activities:
            click.echo("No activities found")
            return
        
        # Filter out already exported activities if resuming
        start_index = progress["last_activity_index"] if resume else 0
        remaining_activities = activities[start_index:]
        
        if not remaining_activities:
            click.echo("✓ All activities already exported")
            return
        
        click.echo(f"\nExporting {len(remaining_activities)} activities to GPX...")
        click.echo(f"Rate limiting: {self.delay}s delay between requests")
        
        success_count = len(progress["exported_activities"])
        total_activities = len(activities)
        
        for i, activity in enumerate(remaining_activities, start=start_index):
            activity_num = i + 1
            click.echo(f"\n[{activity_num}/{total_activities}] Processing activity {activity['id']}...")
            
            if self.export_activity_to_gpx(activity, output_dir, organize_by_type):
                success_count += 1
                progress["exported_activities"].append(activity['id'])
                progress["last_activity_index"] = i
                
                # Save progress every 5 activities
                if len(progress["exported_activities"]) % 5 == 0:
                    self.save_progress(progress_file, progress)
            
            # Show rate limit status periodically
            if activity_num % 10 == 0:
                fifteen_min_pct = (self.rate_limit_info["15min_usage"] / self.rate_limit_info["15min_limit"]) * 100
                daily_pct = (self.rate_limit_info["daily_usage"] / self.rate_limit_info["daily_limit"]) * 100
                click.echo(f"📊 Rate limit usage: {fifteen_min_pct:.1f}% (15min), {daily_pct:.1f}% (daily)")
        
        # Clean up progress file on successful completion
        if success_count == total_activities and os.path.exists(progress_file):
            os.remove(progress_file)
        else:
            self.save_progress(progress_file, progress)
        
        click.echo(f"\n✓ Successfully exported {success_count}/{total_activities} activities")
        if success_count > 0:
            click.echo(f"GPX files saved in: {os.path.abspath(output_dir)}")
        
        if success_count < total_activities:
            click.echo(f"💡 To resume: add --resume flag to continue from where you left off")

@click.command()
@click.option("--client-id", 
              envvar="STRAVA_CLIENT_ID",
              help="Strava API client ID (or set STRAVA_CLIENT_ID env var)")
@click.option("--client-secret", 
              envvar="STRAVA_CLIENT_SECRET",
              help="Strava API client secret (or set STRAVA_CLIENT_SECRET env var)")
@click.option("--refresh-token", 
              envvar="STRAVA_REFRESH_TOKEN",
              help="Strava refresh token (or set STRAVA_REFRESH_TOKEN env var)")
@click.option("--count", 
              default=10, 
              type=int,
              help="Number of recent activities to export (default: 10)")
@click.option("--output-dir", 
              default="gpx_exports",
              help="Output directory for GPX files (default: gpx_exports)")
@click.option("--organize-by-type", 
              is_flag=True,
              help="Create subdirectories for each activity type")
@click.option("--delay", 
              default=1.0,
              type=float,
              help="Delay between requests in seconds (default: 1.0)")
@click.option("--resume", 
              is_flag=True,
              help="Resume interrupted export from where it left off")
def main(client_id, client_secret, refresh_token, count, output_dir, organize_by_type, delay, resume):
    """Export Strava activities as GPX files.
    
    This tool exports recent activities from your Strava account as GPX files.
    You need to provide Strava API credentials either via environment variables
    or command line options.
    
    Setup:
    1. Create a Strava API application at https://www.strava.com/settings/api
    2. Set environment variables or use command line options
    3. Install dependencies: pip install requests gpxpy click
    """
    
    # Check if all credentials are provided
    if not all([client_id, client_secret, refresh_token]):
        click.echo("⚠ Missing Strava API credentials!", err=True)
        click.echo("\nOptions to provide credentials:")
        click.echo("1. Environment variables:")
        click.echo("   export STRAVA_CLIENT_ID='your_client_id'")
        click.echo("   export STRAVA_CLIENT_SECRET='your_client_secret'")
        click.echo("   export STRAVA_REFRESH_TOKEN='your_refresh_token'")
        click.echo("\n2. Command line options:")
        click.echo("   python strava-export.py --client-id ID --client-secret SECRET --refresh-token TOKEN")
        click.echo("\nTo get credentials:")
        click.echo("1. Go to https://www.strava.com/settings/api")
        click.echo("2. Create a new application")
        click.echo("3. Follow OAuth flow to get refresh token")
        raise click.Abort()
    
    # Create exporter and run
    exporter = StravaExporter(client_id, client_secret, refresh_token, delay=delay)
    exporter.export_recent_activities(count=count, output_dir=output_dir, organize_by_type=organize_by_type, resume=resume)

if __name__ == "__main__":
    main()