"""Shared support package for the advanced suites.

Modules here are imported by both pytest modes and standalone ``entry.py``
scripts.  Keep this package free of pytest and FastAPI imports so it can be
reused outside a pytest process.
"""
