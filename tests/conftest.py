"""Pytest configuration and shared fixtures."""

import os

# Force demo mode for all tests
os.environ["DEMO_MODE"] = "true"
