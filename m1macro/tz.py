"""Time zones from the pinned tzdata package only (Impl Part 4 §1): the system zoneinfo is never used."""
import zoneinfo

zoneinfo.reset_tzpath(to=[])
JST = zoneinfo.ZoneInfo("Asia/Tokyo")
ET = zoneinfo.ZoneInfo("America/New_York")
UTC = zoneinfo.ZoneInfo("UTC")


def tzdata_version():
    import tzdata
    return getattr(tzdata, "IANA_VERSION", tzdata.__version__)
