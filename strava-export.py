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

class StravaExporter:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.base_url = "https://www.strava.com/api/v3"
        
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
    
    def get_recent_activities(self, per_page: int = 30) -> List[Dict]:
        """Fetch recent activities from Strava"""
        try:
            response = requests.get(
                f"{self.base_url}/athlete/activities",
                headers=self.get_headers(),
                params={"per_page": per_page}
            )
            response.raise_for_status()
            activities = response.json()
            click.echo(f"✓ Found {len(activities)} recent activities")
            return activities
        except requests.exceptions.RequestException as e:
            click.echo(f"✗ Failed to fetch activities: {e}", err=True)
            return []
    
    def get_activity_streams(self, activity_id: int) -> Optional[Dict]:
        """Get activity stream data (coordinates, time, etc.)"""
        try:
            response = requests.get(
                f"{self.base_url}/activities/{activity_id}/streams",
                headers=self.get_headers(),
                params={
                    "keys": "latlng,time,altitude,distance,heartrate,cadence,watts",
                    "key_by_type": "true"
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            click.echo(f"✗ Failed to get streams for activity {activity_id}: {e}", err=True)
            return None
    
    def create_gpx_from_streams(self, activity: Dict, streams: Dict) -> Optional[gpxpy.gpx.GPX]:
        """Convert Strava activity streams to GPX format"""
        if not streams or "latlng" not in streams:
            click.echo(f"  ⚠ No GPS data available for activity {activity['id']}")
            return None
            
        gpx = gpxpy.gpx.GPX()
        gpx.name = activity.get("name", f"Activity {activity['id']}")
        gpx.description = f"Exported from Strava - {activity.get('type', 'Unknown')} activity"
        
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
                point.time = start_time.replace(second=start_time.second + time_data[i])
            
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
    
    def export_activity_to_gpx(self, activity: Dict, output_dir: str = "gpx_exports") -> bool:
        """Export a single activity to GPX file"""
        activity_id = activity["id"]
        activity_name = activity.get("name", f"Activity {activity_id}")
        
        click.echo(f"  Processing: {activity_name}")
        
        # Get activity streams
        streams = self.get_activity_streams(activity_id)
        if not streams:
            return False
        
        # Create GPX from streams
        gpx = self.create_gpx_from_streams(activity, streams)
        if not gpx:
            return False
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename
        start_date = datetime.fromisoformat(activity["start_date_local"].replace("Z", "+00:00"))
        safe_name = "".join(c for c in activity_name if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
        filename = f"{start_date.strftime('%Y%m%d_%H%M')}_{safe_name}.gpx"
        filepath = os.path.join(output_dir, filename)
        
        # Write GPX file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(gpx.to_xml())
            click.echo(f"  ✓ Saved: {filepath}")
            return True
        except Exception as e:
            click.echo(f"  ✗ Failed to save {filepath}: {e}", err=True)
            return False
    
    def export_recent_activities(self, count: int = 10, output_dir: str = "gpx_exports"):
        """Export recent activities to GPX files"""
        if not self.get_access_token():
            return
        
        click.echo(f"Fetching {count} recent activities...")
        activities = self.get_recent_activities(count)
        
        if not activities:
            click.echo("No activities found")
            return
        
        click.echo(f"\nExporting {len(activities)} activities to GPX...")
        success_count = 0
        
        for activity in activities:
            if self.export_activity_to_gpx(activity, output_dir):
                success_count += 1
        
        click.echo(f"\n✓ Successfully exported {success_count}/{len(activities)} activities")
        if success_count > 0:
            click.echo(f"GPX files saved in: {os.path.abspath(output_dir)}")

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
def main(client_id, client_secret, refresh_token, count, output_dir):
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
    exporter = StravaExporter(client_id, client_secret, refresh_token)
    exporter.export_recent_activities(count=count, output_dir=output_dir)

if __name__ == "__main__":
    main()