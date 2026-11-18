"""Tests run on the small synthetic city so they are fast and independent of the OpenStreetMap data.

The ML detectors take a few seconds to train, so they are off by default in tests (ARMOUR_ML=0); the tests that need them
ask for them explicitly.
"""
import os

os.environ.setdefault("ARMOUR_CITY", "synthetic")
os.environ.setdefault("ARMOUR_ML", "0")
