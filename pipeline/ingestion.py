"""Backward-compatible CSV entry point to the local source abstraction."""
from pipeline.source import load_source

def load_posts(csv_path):
    return load_source("csv", csv_path)
