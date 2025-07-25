# -*- coding: utf-8 -*-
"""Untitled1.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1merKtgrZbFwk031G3334DaWV0SjcWFRk
"""

import os
import requests
import json
import pandas as pd
import logging
import time
from dataclasses import dataclass
# Test comment
@dataclass
class Config:
    api_key: str = os.getenv("TMDBAPIKEY", "d0a624b2f4c6bdd8d531183a98bd0eef")
    max_pages: int = 15
    retry_count: int = 3
    retry_delay: int = 2
    sleep_time: float = 0.25
    output_file: str = "popular_movies.json"
    checkpoint_file: str = "checkpoint.json"
    checkpoint_frequency: int = 20
    log_file: str = "etl_log.txt"
    fail_threshold: int = 10
    resume_last: bool = True

CONFIG = Config()

logging.basicConfig(
    filename=CONFIG.log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def retry_request(url):
    for attempt in range(CONFIG.retry_count):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logging.warning(f"Non-200 status {response.status_code} for URL: {url}")
        except Exception as e:
            logging.error(f"Error fetching URL: {url} | Exception: {e}")
        time.sleep(CONFIG.retry_delay ** attempt)
    return None

def get_movie_data(page):
    url = f"https://api.themoviedb.org/3/movie/popular?api_key={CONFIG.api_key}&language=en-US&page={page}"
    return retry_request(url)

def get_movie_details(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={CONFIG.api_key}&language=en-US"
    return retry_request(url)

def get_movie_credits(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={CONFIG.api_key}"
    return retry_request(url)

def load_checkpoint():
    if CONFIG.resume_last and os.path.exists(CONFIG.checkpoint_file):
        with open(CONFIG.checkpoint_file, "r") as file:
            return json.load(file)
    return None

def save_checkpoint(last_page):
    with open(CONFIG.checkpoint_file, "w") as file:
        json.dump({"last_page": last_page}, file)

def save_data(data):
    with open(CONFIG.output_file, "w") as file:
        json.dump(data, file, indent=2)

def transform_movie_data(detail, credit):
    director = next((c["name"] for c in credit.get("crew", []) if c.get("job") == "Director"), None)
    cast = [c["name"] for c in credit.get("cast", [])[:3]]

    return {
        "id": detail.get("id"),
        "title": detail.get("title"),
        "original_title": detail.get("original_title"),
        "release_date": detail.get("release_date"),
        "budget": detail.get("budget"),
        "revenue": detail.get("revenue"),
        "runtime": detail.get("runtime"),
        "genres": ", ".join([g["name"] for g in detail.get("genres", [])]),
        "popularity": detail.get("popularity"),
        "vote_avg": detail.get("vote_average"),
        "vote_count": detail.get("vote_count"),
        "director": director,
        "cast1": cast[0] if len(cast) > 0 else None,
        "cast2": cast[1] if len(cast) > 1 else None,
        "cast3": cast[2] if len(cast) > 2 else None
    }

def etl_job():
    movies = []
    fail_count = 0

    checkpoint = load_checkpoint()
    start_page = checkpoint["last_page"] + 1 if checkpoint else 1

    for page in range(start_page, CONFIG.max_pages + 1):
        logging.info(f"Fetching page {page}")
        popular_movies = get_movie_data(page)

        if not popular_movies:
            fail_count += 1
            logging.warning(f"Failed to fetch popular movies for page {page}")
            if fail_count >= CONFIG.fail_threshold:
                logging.error("Too many failures. Aborting ETL job.")
                break
            continue

        for movie in popular_movies.get("results", []):
            movie_id = movie.get("id")
            details = get_movie_details(movie_id)
            credits = get_movie_credits(movie_id)

            if not details or not credits:
                fail_count += 1
                logging.warning(f"Skipping movie {movie_id} due to missing data")
                continue

            transformed = transform_movie_data(details, credits)
            movies.append(transformed)

            if len(movies) % CONFIG.checkpoint_frequency == 0:
                save_checkpoint(page)
                save_data(movies)
                logging.info(f"Checkpoint saved at {len(movies)} movies")

            time.sleep(CONFIG.sleep_time)

    save_data(movies)
    save_checkpoint(CONFIG.max_pages)
    logging.info("ETL job completed successfully")

if __name__ == "__main__":
    etl_job()