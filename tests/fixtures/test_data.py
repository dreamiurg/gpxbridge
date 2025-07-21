"""
Test data factories and fixtures for GPXBridge tests
"""

import gpxpy
import gpxpy.gpx
from typing import Dict, List, Any
from datetime import datetime, timedelta


class GPXTestDataFactory:
    """Factory for creating test GPX data"""

    @staticmethod
    def create_simple_gpx() -> gpxpy.gpx.GPX:
        """Create a simple GPX with basic track data"""
        gpx = gpxpy.gpx.GPX()
        gpx.name = "Test Track"
        gpx.description = "A simple test track"

        # Create track
        track = gpxpy.gpx.GPXTrack()
        track.name = "Simple Track"
        gpx.tracks.append(track)

        # Create segment
        segment = gpxpy.gpx.GPXTrackSegment()
        track.segments.append(segment)

        # Add some points
        points = [
            (47.6062, -122.3321, 56.0),  # Seattle
            (47.6205, -122.3493, 78.0),  # Queen Anne
            (47.6097, -122.3331, 45.0),  # Pike Place
        ]

        for i, (lat, lng, elev) in enumerate(points):
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=lat,
                longitude=lng,
                elevation=elev,
                time=datetime(2024, 1, 15, 10, i * 5, 0),  # 5 minutes apart
            )
            segment.points.append(point)

        return gpx

    @staticmethod
    def create_multi_track_gpx() -> gpxpy.gpx.GPX:
        """Create GPX with multiple tracks"""
        gpx = gpxpy.gpx.GPX()
        gpx.name = "Multi-Track Test"

        # First track
        track1 = gpxpy.gpx.GPXTrack()
        track1.name = "Track 1"
        gpx.tracks.append(track1)

        segment1 = gpxpy.gpx.GPXTrackSegment()
        track1.segments.append(segment1)

        # Seattle area points
        for i in range(3):
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=47.6062 + i * 0.01,
                longitude=-122.3321 + i * 0.01,
                elevation=50.0 + i * 10,
                time=datetime(2024, 1, 15, 10, i * 2, 0),
            )
            segment1.points.append(point)

        # Second track
        track2 = gpxpy.gpx.GPXTrack()
        track2.name = "Track 2"
        gpx.tracks.append(track2)

        segment2 = gpxpy.gpx.GPXTrackSegment()
        track2.segments.append(segment2)

        # Portland area points
        for i in range(2):
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=45.5152 + i * 0.01,
                longitude=-122.6784 + i * 0.01,
                elevation=100.0 + i * 20,
                time=datetime(2024, 1, 15, 11, i * 3, 0),
            )
            segment2.points.append(point)

        return gpx

    @staticmethod
    def create_multi_segment_gpx() -> gpxpy.gpx.GPX:
        """Create GPX with single track but multiple segments"""
        gpx = gpxpy.gpx.GPX()
        gpx.name = "Multi-Segment Test"

        track = gpxpy.gpx.GPXTrack()
        track.name = "Segmented Track"
        gpx.tracks.append(track)

        # First segment
        segment1 = gpxpy.gpx.GPXTrackSegment()
        track.segments.append(segment1)

        for i in range(3):
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=47.6062 + i * 0.005,
                longitude=-122.3321 + i * 0.005,
                elevation=50.0 + i * 5,
                time=datetime(2024, 1, 15, 10, i, 0),
            )
            segment1.points.append(point)

        # Second segment (gap in track)
        segment2 = gpxpy.gpx.GPXTrackSegment()
        track.segments.append(segment2)

        for i in range(2):
            point = gpxpy.gpx.GPXTrackPoint(
                latitude=47.6200 + i * 0.005,
                longitude=-122.3500 + i * 0.005,
                elevation=80.0 + i * 5,
                time=datetime(2024, 1, 15, 10, 10 + i, 0),  # 10 minute gap
            )
            segment2.points.append(point)

        return gpx

    @staticmethod
    def create_empty_gpx() -> gpxpy.gpx.GPX:
        """Create empty GPX (no tracks)"""
        gpx = gpxpy.gpx.GPX()
        gpx.name = "Empty Test GPX"
        gpx.description = "GPX with no tracks for testing"
        return gpx

    @staticmethod
    def create_track_no_points_gpx() -> gpxpy.gpx.GPX:
        """Create GPX with track but no points"""
        gpx = gpxpy.gpx.GPX()
        gpx.name = "No Points Test"

        track = gpxpy.gpx.GPXTrack()
        track.name = "Empty Track"
        gpx.tracks.append(track)

        segment = gpxpy.gpx.GPXTrackSegment()
        track.segments.append(segment)
        # No points added to segment

        return gpx


class StravaTestDataFactory:
    """Factory for creating test Strava data"""

    @staticmethod
    def create_basic_activity() -> Dict[str, Any]:
        """Create basic Strava activity data"""
        return {
            "id": 12345,
            "name": "Morning Run",
            "type": "Run",
            "start_date_local": "2024-01-15T07:30:00",
            "distance": 5000.0,
            "moving_time": 1800,
            "total_elevation_gain": 100.0,
        }

    @staticmethod
    def create_activity_with_streams() -> Dict[str, Any]:
        """Create Strava activity data with corresponding streams"""
        activity = StravaTestDataFactory.create_basic_activity()

        # Mock streams data
        streams = {
            "latlng": {
                "data": [
                    [47.6062, -122.3321],
                    [47.6072, -122.3331],
                    [47.6082, -122.3341],
                    [47.6092, -122.3351],
                ],
                "resolution": "high",
            },
            "time": {
                "data": [0, 300, 600, 900],  # 5-minute intervals
                "resolution": "high",
            },
            "altitude": {"data": [56.0, 58.0, 62.0, 65.0], "resolution": "high"},
            "distance": {"data": [0.0, 1250.0, 2500.0, 3750.0], "resolution": "high"},
        }

        return {"activity": activity, "streams": streams}

    @staticmethod
    def create_activities_list(count: int = 5) -> List[Dict[str, Any]]:
        """Create a list of Strava activities for testing"""
        activities = []
        base_date = datetime(2024, 1, 15, 7, 30, 0)

        activity_types = ["Run", "Ride", "Hike", "Swim", "Walk"]

        for i in range(count):
            activity_date = base_date + timedelta(days=i)
            activity = {
                "id": 12345 + i,
                "name": f"Activity {i + 1}",
                "type": activity_types[i % len(activity_types)],
                "start_date_local": activity_date.isoformat(),
                "distance": 1000.0 * (i + 1),
                "moving_time": 600 * (i + 1),
                "total_elevation_gain": 50.0 * i,
            }
            activities.append(activity)

        return activities

    @staticmethod
    def create_invalid_activities() -> List[Dict[str, Any]]:
        """Create invalid Strava activity data for testing validation"""
        return [
            # Invalid ID
            {
                "id": -1,
                "name": "Test",
                "type": "Run",
                "start_date_local": "2024-01-15T07:30:00",
            },
            # Invalid name
            {
                "id": 1,
                "name": "",
                "type": "Run",
                "start_date_local": "2024-01-15T07:30:00",
            },
            {
                "id": 2,
                "name": "   ",
                "type": "Run",
                "start_date_local": "2024-01-15T07:30:00",
            },
            {
                "id": 3,
                "name": "A" * 201,
                "type": "Run",
                "start_date_local": "2024-01-15T07:30:00",
            },
            # Invalid type
            {
                "id": 4,
                "name": "Test",
                "type": "",
                "start_date_local": "2024-01-15T07:30:00",
            },
            {
                "id": 5,
                "name": "Test",
                "type": "A" * 51,
                "start_date_local": "2024-01-15T07:30:00",
            },
            # Invalid date
            {
                "id": 6,
                "name": "Test",
                "type": "Run",
                "start_date_local": "invalid-date",
            },
            {"id": 7, "name": "Test", "type": "Run", "start_date_local": ""},
            # Invalid numeric fields
            {
                "id": 8,
                "name": "Test",
                "type": "Run",
                "start_date_local": "2024-01-15T07:30:00",
                "distance": -1,
            },
            {
                "id": 9,
                "name": "Test",
                "type": "Run",
                "start_date_local": "2024-01-15T07:30:00",
                "moving_time": -1,
            },
            {
                "id": 10,
                "name": "Test",
                "type": "Run",
                "start_date_local": "2024-01-15T07:30:00",
                "total_elevation_gain": -1,
            },
        ]


class CoordinateTestDataFactory:
    """Factory for creating coordinate test data"""

    @staticmethod
    def get_valid_coordinates() -> List[tuple]:
        """Get list of valid GPS coordinates"""
        return [
            (0.0, 0.0),  # Equator, Prime Meridian
            (45.0, -122.0),  # Portland area
            (90.0, 180.0),  # North Pole, International Date Line
            (-90.0, -180.0),  # South Pole, opposite side
            (47.6062, -122.3321),  # Seattle
            (40.7128, -74.0060),  # New York
            (51.5074, -0.1278),  # London
            (35.6762, 139.6503),  # Tokyo
            (-33.8688, 151.2093),  # Sydney
        ]

    @staticmethod
    def get_invalid_coordinates() -> List[tuple]:
        """Get list of invalid GPS coordinates"""
        return [
            (91.0, 0.0),  # Latitude too high
            (-91.0, 0.0),  # Latitude too low
            (0.0, 181.0),  # Longitude too high
            (0.0, -181.0),  # Longitude too low
            (float("inf"), 0.0),  # Infinite latitude
            (0.0, float("nan")),  # NaN longitude
            (100.0, 200.0),  # Both out of bounds
            (-100.0, -200.0),  # Both out of bounds (negative)
        ]

    @staticmethod
    def get_edge_case_coordinates() -> List[tuple]:
        """Get edge case coordinates for boundary testing"""
        return [
            (89.999999, 179.999999),  # Just within bounds
            (-89.999999, -179.999999),  # Just within bounds (negative)
            (90.0, 180.0),  # Exact boundaries
            (-90.0, -180.0),  # Exact boundaries (negative)
            (0.000001, 0.000001),  # Very small positive
            (-0.000001, -0.000001),  # Very small negative
        ]


class PathTestDataFactory:
    """Factory for creating path test data"""

    @staticmethod
    def get_safe_paths() -> List[str]:
        """Get list of safe output paths"""
        return [
            "./exports",
            "exports",
            "data/gpx",
            "./my_exports",
            "test_output",
            "../sibling_dir/exports",
            "nested/deep/exports",
        ]

    @staticmethod
    def get_dangerous_paths() -> List[str]:
        """Get list of potentially dangerous paths"""
        return [
            "../../../etc/passwd",
            "../../../../../../etc/shadow",
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "/var/log/system.log",
            "../../../../windows/system32",
            "/proc/version",
            "../../../../../../../dev/null",
        ]

    @staticmethod
    def get_invalid_paths() -> List[str]:
        """Get list of invalid or problematic paths"""
        return [
            "",  # Empty path
            "   ",  # Whitespace only
            "con",  # Windows reserved name
            "aux",  # Windows reserved name
            "prn",  # Windows reserved name
            "nul",  # Windows reserved name
            "path\x00with\x00nulls",  # Null bytes
            "path\nwith\nnewlines",  # Control characters
        ]
