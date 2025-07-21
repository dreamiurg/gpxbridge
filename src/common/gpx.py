"""
Basic GPX utilities shared across all GPS services
"""

import gpxpy
import gpxpy.gpx


class GPXUtils:
    """Basic GPX utilities for creating and validating GPX files"""

    @staticmethod
    def create_empty_gpx(
        name: str = "GPS Track", description: str = ""
    ) -> gpxpy.gpx.GPX:
        """Create an empty GPX object with basic metadata"""
        gpx = gpxpy.gpx.GPX()
        gpx.name = name
        gpx.description = description
        return gpx

    @staticmethod
    def create_track(gpx: gpxpy.gpx.GPX, track_name: str) -> gpxpy.gpx.GPXTrack:
        """Create and add a new track to a GPX object"""
        track = gpxpy.gpx.GPXTrack()
        track.name = track_name
        gpx.tracks.append(track)
        return track

    @staticmethod
    def create_segment(track: gpxpy.gpx.GPXTrack) -> gpxpy.gpx.GPXTrackSegment:
        """Create and add a new segment to a track"""
        segment = gpxpy.gpx.GPXTrackSegment()
        track.segments.append(segment)
        return segment

    @staticmethod
    def validate_gpx_string(gpx_string: str) -> bool:
        """Validate that a string contains valid GPX XML"""
        try:
            if not gpx_string or not gpx_string.strip():
                return False

            # Check if the string actually contains a GPX root element
            if "<gpx" not in gpx_string.lower():
                return False

            # Parse the GPX string
            gpx = gpxpy.parse(gpx_string)

            # Ensure it's actually a GPX object (not just any XML)
            return isinstance(gpx, gpxpy.gpx.GPX)
        except Exception:
            return False

    @staticmethod
    def get_gpx_stats(gpx: gpxpy.gpx.GPX) -> dict:
        """Get basic statistics from a GPX object"""
        stats = {
            "tracks": len(gpx.tracks),
            "total_points": 0,
            "total_distance": 0.0,
            "total_elevation_gain": 0.0,
        }

        for track in gpx.tracks:
            # Count points first
            for segment in track.segments:
                stats["total_points"] += len(segment.points)

            # Only calculate stats if track has points
            if any(len(segment.points) > 0 for segment in track.segments):
                # Get track length (distance)
                track_length = track.length_3d() or track.length_2d() or 0
                stats["total_distance"] += track_length

                # Get elevation gain
                uphill, _ = track.get_uphill_downhill()
                stats["total_elevation_gain"] += uphill or 0

        return stats
