#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --upgrade pip
pip install Flask>=3.0.0 Flask-SQLAlchemy>=3.1.1 Flask-Cors>=4.0.0 gunicorn>=22.0.0 python-dotenv>=1.0.0 requests>=2.32.0 PyJWT>=2.8.0 yfinance>=0.2.40 google-generativeai>=0.5.0 pandas numpy psycopg2-binary