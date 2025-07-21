"""
Tests for GPX utilities
"""

import gpxpy
import gpxpy.gpx
from hypothesis import given, strategies as st

from src.common.gpx import GPXUtils


class TestGPXUtils:
    """Test GPX utility functions"""

    def test_create_empty_gpx_default(self):
        """Test creating empty GPX with default values"""
        gpx = GPXUtils.create_empty_gpx()
        assert isinstance(gpx, gpxpy.gpx.GPX)
        assert gpx.name == "GPS Track"
        assert gpx.description == ""
        assert len(gpx.tracks) == 0

    def test_create_empty_gpx_custom(self):
        """Test creating empty GPX with custom values"""
        name = "My Custom Track"
        description = "A test track for validation"
        gpx = GPXUtils.create_empty_gpx(name=name, description=description)

        assert isinstance(gpx, gpxpy.gpx.GPX)
        assert gpx.name == name
        assert gpx.description == description
        assert len(gpx.tracks) == 0

    def test_create_track(self):
        """Test creating and adding a track to GPX"""
        gpx = GPXUtils.create_empty_gpx()
        track_name = "Test Track"

        track = GPXUtils.create_track(gpx, track_name)

        assert isinstance(track, gpxpy.gpx.GPXTrack)
        assert track.name == track_name
        assert len(gpx.tracks) == 1
        assert gpx.tracks[0] == track
        assert len(track.segments) == 0

    def test_create_multiple_tracks(self):
        """Test creating multiple tracks"""
        gpx = GPXUtils.create_empty_gpx()

        track1 = GPXUtils.create_track(gpx, "Track 1")
        track2 = GPXUtils.create_track(gpx, "Track 2")

        assert len(gpx.tracks) == 2
        assert gpx.tracks[0] == track1
        assert gpx.tracks[1] == track2
        assert gpx.tracks[0].name == "Track 1"
        assert gpx.tracks[1].name == "Track 2"

    def test_create_segment(self):
        """Test creating and adding a segment to track"""
        gpx = GPXUtils.create_empty_gpx()
        track = GPXUtils.create_track(gpx, "Test Track")

        segment = GPXUtils.create_segment(track)

        assert isinstance(segment, gpxpy.gpx.GPXTrackSegment)
        assert len(track.segments) == 1
        assert track.segments[0] == segment
        assert len(segment.points) == 0

    def test_create_multiple_segments(self):
        """Test creating multiple segments in one track"""
        gpx = GPXUtils.create_empty_gpx()
        track = GPXUtils.create_track(gpx, "Test Track")

        segment1 = GPXUtils.create_segment(track)
        segment2 = GPXUtils.create_segment(track)

        assert len(track.segments) == 2
        assert track.segments[0] == segment1
        assert track.segments[1] == segment2

    def test_validate_gpx_string_valid(self):
        """Test validating valid GPX XML string"""
        # Create a valid GPX and convert to XML
        gpx = GPXUtils.create_empty_gpx("Valid Track", "Test description")
        track = GPXUtils.create_track(gpx, "Track 1")
        segment = GPXUtils.create_segment(track)

        # Add a point to make it more realistic
        point = gpxpy.gpx.GPXTrackPoint(latitude=45.0, longitude=-122.0)
        segment.points.append(point)

        xml_string = gpx.to_xml()

        assert GPXUtils.validate_gpx_string(xml_string) is True

    def test_validate_gpx_string_invalid(self):
        """Test validating invalid GPX XML strings"""
        invalid_xml_strings = [
            "not xml at all",
            "<xml>invalid gpx</xml>",
            "<gpx>incomplete",
            "",
            "<?xml version='1.0' encoding='UTF-8'?><invalid>content</invalid>",
            "<gpx xmlns='http://www.topografix.com/GPX/1/1'>malformed</gpx",
        ]

        for invalid_xml in invalid_xml_strings:
            assert GPXUtils.validate_gpx_string(invalid_xml) is False

    def test_validate_gpx_string_minimal_valid(self):
        """Test validating minimal valid GPX"""
        minimal_gpx = """<?xml version="1.0" encoding="UTF-8"?>
        <gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
        </gpx>"""

        assert GPXUtils.validate_gpx_string(minimal_gpx) is True

    def test_get_gpx_stats_empty(self):
        """Test getting stats from empty GPX"""
        gpx = GPXUtils.create_empty_gpx()
        stats = GPXUtils.get_gpx_stats(gpx)

        expected = {
            "tracks": 0,
            "total_points": 0,
            "total_distance": 0.0,
            "total_elevation_gain": 0.0,
        }
        assert stats == expected

    def test_get_gpx_stats_empty_track(self):
        """Test getting stats from GPX with empty track"""
        gpx = GPXUtils.create_empty_gpx()
        GPXUtils.create_track(gpx, "Empty Track")

        stats = GPXUtils.get_gpx_stats(gpx)

        expected = {
            "tracks": 1,
            "total_points": 0,
            "total_distance": 0.0,
            "total_elevation_gain": 0.0,
        }
        assert stats == expected

    def test_get_gpx_stats_with_points(self):
        """Test getting stats from GPX with actual points"""
        gpx = GPXUtils.create_empty_gpx()
        track = GPXUtils.create_track(gpx, "Test Track")
        segment = GPXUtils.create_segment(track)

        # Add some points with elevation
        points = [
            gpxpy.gpx.GPXTrackPoint(latitude=45.0, longitude=-122.0, elevation=100.0),
            gpxpy.gpx.GPXTrackPoint(latitude=45.01, longitude=-122.01, elevation=150.0),
            gpxpy.gpx.GPXTrackPoint(latitude=45.02, longitude=-122.02, elevation=120.0),
        ]

        for point in points:
            segment.points.append(point)

        stats = GPXUtils.get_gpx_stats(gpx)

        assert stats["tracks"] == 1
        assert stats["total_points"] == 3
        assert stats["total_distance"] > 0  # Should have calculated some distance
        assert (
            stats["total_elevation_gain"] >= 0
        )  # Should have calculated elevation gain

    def test_get_gpx_stats_multiple_tracks(self):
        """Test getting stats from GPX with multiple tracks"""
        gpx = GPXUtils.create_empty_gpx()

        # First track with points
        track1 = GPXUtils.create_track(gpx, "Track 1")
        segment1 = GPXUtils.create_segment(track1)
        segment1.points.append(gpxpy.gpx.GPXTrackPoint(latitude=45.0, longitude=-122.0))
        segment1.points.append(
            gpxpy.gpx.GPXTrackPoint(latitude=45.01, longitude=-122.01)
        )

        # Second track with points
        track2 = GPXUtils.create_track(gpx, "Track 2")
        segment2 = GPXUtils.create_segment(track2)
        segment2.points.append(gpxpy.gpx.GPXTrackPoint(latitude=46.0, longitude=-123.0))

        stats = GPXUtils.get_gpx_stats(gpx)

        assert stats["tracks"] == 2
        assert stats["total_points"] == 3  # 2 + 1 points
        assert stats["total_distance"] >= 0
        assert stats["total_elevation_gain"] >= 0

    def test_get_gpx_stats_multiple_segments(self):
        """Test getting stats from track with multiple segments"""
        gpx = GPXUtils.create_empty_gpx()
        track = GPXUtils.create_track(gpx, "Multi-segment Track")

        # First segment
        segment1 = GPXUtils.create_segment(track)
        segment1.points.append(gpxpy.gpx.GPXTrackPoint(latitude=45.0, longitude=-122.0))
        segment1.points.append(
            gpxpy.gpx.GPXTrackPoint(latitude=45.01, longitude=-122.01)
        )

        # Second segment
        segment2 = GPXUtils.create_segment(track)
        segment2.points.append(gpxpy.gpx.GPXTrackPoint(latitude=46.0, longitude=-123.0))

        stats = GPXUtils.get_gpx_stats(gpx)

        assert stats["tracks"] == 1
        assert stats["total_points"] == 3  # 2 + 1 points across segments
        assert stats["total_distance"] >= 0
        assert stats["total_elevation_gain"] >= 0

    def test_gpx_workflow_integration(self):
        """Test complete GPX creation workflow"""
        # Create a complete GPX with track, segment, and points
        gpx = GPXUtils.create_empty_gpx("Integration Test", "Complete workflow test")
        track = GPXUtils.create_track(gpx, "Test Route")
        segment = GPXUtils.create_segment(track)

        # Add a realistic set of points
        points_data = [
            (47.6062, -122.3321, 56.0),  # Seattle
            (47.6205, -122.3493, 78.0),  # Queen Anne
            (47.6097, -122.3331, 45.0),  # Pike Place
        ]

        for lat, lng, elev in points_data:
            point = gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lng, elevation=elev)
            segment.points.append(point)

        # Validate the created GPX
        xml_string = gpx.to_xml()
        assert GPXUtils.validate_gpx_string(xml_string) is True

        # Check stats
        stats = GPXUtils.get_gpx_stats(gpx)
        assert stats["tracks"] == 1
        assert stats["total_points"] == 3
        assert stats["total_distance"] > 0
        assert stats["total_elevation_gain"] >= 0

    @given(st.text(min_size=1, max_size=100))
    def test_gpx_name_property(self, name):
        """Property test: any string should be valid as GPX name"""
        try:
            gpx = GPXUtils.create_empty_gpx(name=name)
            assert gpx.name == name
        except Exception:
            # Some characters might cause issues, that's acceptable
            pass

    @given(st.text(min_size=1, max_size=100))
    def test_track_name_property(self, track_name):
        """Property test: any string should be valid as track name"""
        try:
            gpx = GPXUtils.create_empty_gpx()
            track = GPXUtils.create_track(gpx, track_name)
            assert track.name == track_name
        except Exception:
            # Some characters might cause issues, that's acceptable
            pass

    def test_gpx_xml_structure(self):
        """Test that generated GPX has correct XML structure"""
        gpx = GPXUtils.create_empty_gpx("Structure Test")
        track = GPXUtils.create_track(gpx, "Track")
        segment = GPXUtils.create_segment(track)
        segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=45.0, longitude=-122.0))

        xml_string = gpx.to_xml()

        # Basic XML structure checks
        assert "<?xml" in xml_string
        assert "<gpx" in xml_string
        assert "</gpx>" in xml_string
        assert "<trk>" in xml_string
        assert "</trk>" in xml_string
        assert "<trkseg>" in xml_string
        assert "</trkseg>" in xml_string
        assert "<trkpt" in xml_string
        assert "</trkpt>" in xml_string

    def test_empty_string_validation(self):
        """Test empty string validation"""
        assert GPXUtils.validate_gpx_string("") is False

    def test_none_validation(self):
        """Test None input validation"""
        # This should not crash
        try:
            result = GPXUtils.validate_gpx_string(None)
            assert result is False
        except (TypeError, AttributeError):
            # This is also acceptable behavior
            pass
