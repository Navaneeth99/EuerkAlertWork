"""DuckDB setup for EurekAlert analysis. Usage: python code/05_eurekalert_duckdb.py setup"""
import sys

from utils.eurekalert_duckdb import main

if __name__ == "__main__":
    sys.exit(main())
