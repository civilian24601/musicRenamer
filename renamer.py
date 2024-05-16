import os
import re
import json
import requests
import logging
import time
from mutagen.easyid3 import EasyID3
from dotenv import load_dotenv
from Levenshtein import ratio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

DISCOGS_TOKEN = os.getenv('DISCOGS_ACCESS_TOKEN')
DISCOGS_REQUESTS_PER_MINUTE = 60
DISCOGS_REQUEST_DELAY = 60 / DISCOGS_REQUESTS_PER_MINUTE

last_request_time = 0
requests_this_minute = 0

def sanitize_title(title):
    # Basic cleaning to improve API hit rate
    title = re.sub(r"\[.*?\]|\(.*?\)|\{.*?\}", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title

def call_discogs(artist, album):
    global last_request_time, requests_this_minute

    current_time = time.time()
    elapsed_time = current_time - last_request_time

    if elapsed_time >= 60:
        # Reset the request count if more than 60 seconds have passed
        requests_this_minute = 0
        last_request_time = current_time

    if requests_this_minute >= DISCOGS_REQUESTS_PER_MINUTE:
        # If we've reached the limit, wait until the next 60-second window
        time.sleep(60 - elapsed_time)
        requests_this_minute = 0
        last_request_time = time.time()

    headers = {'Authorization': f'Discogs token={DISCOGS_TOKEN}'}
    params = {'q': f'{artist} {album}', 'type': 'release'}
    response = requests.get('https://api.discogs.com/database/search', headers=headers, params=params)

    if response.status_code == 200 and response.json().get('results'):
        result = response.json()['results'][0]
        requests_this_minute += 1
        time.sleep(DISCOGS_REQUEST_DELAY)
        return result['title'], result.get('year', 'Unknown Year')
    else:
        # Log the rate limit headers for debugging purposes
        logging.debug(f"X-Discogs-Ratelimit: {response.headers.get('X-Discogs-Ratelimit')}")
        logging.debug(f"X-Discogs-Ratelimit-Used: {response.headers.get('X-Discogs-Ratelimit-Used')}")
        logging.debug(f"X-Discogs-Ratelimit-Remaining: {response.headers.get('X-Discogs-Ratelimit-Remaining')}")
        requests_this_minute += 1
        time.sleep(DISCOGS_REQUEST_DELAY)
        return None, None

def string_similarity(a, b):
    return ratio(a.lower(), b.lower())

def load_processed_files():
    if os.path.exists('processed_files.json'):
        with open('processed_files.json', 'r') as f:
            return json.load(f)
    return {}

def save_processed_files(processed_files):
    with open('processed_files.json', 'w') as f:
        json.dump(processed_files, f, indent=2)

def process_files(folder_path, confidence_threshold=0.8):
    processed_files = load_processed_files()

    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith('.mp3'):
            original_path = os.path.join(folder_path, file_name)
            file_timestamp = os.path.getmtime(original_path)

            if file_name in processed_files and file_timestamp <= processed_files[file_name]['timestamp']:
                logging.info(f"Skipping already processed file: {file_name}")
                continue

            file_name = file_name[:-4]  # Remove .mp3 for easier processing

            # Clean up the filename
            file_name = re.sub(r'_', ' ', file_name)  # Replace underscores with spaces
            file_name = re.sub(r'(\d+\s*kbps)|(\-\s*\w+\s*\-)', '', file_name, flags=re.IGNORECASE)  # Remove bitrate and YouTube ID
            file_name = re.sub(r'(full album|\[full\s*\]|\(full\s*\))', '', file_name, flags=re.IGNORECASE)  # Remove "Full Album"
            file_name = re.sub(r'(\{\s*\w+\s*\})|(\[\s*\])|(\(\s*\))', '', file_name)  # Remove empty brackets and genre tags
            file_name = re.sub(r'\(.*?\)|\[.*?\]|\{.*?\}', '', file_name)  # Remove any remaining text in brackets
            file_name = re.sub(r'[^a-zA-Z0-9\s\-–—\%\*]', '', file_name)  # Remove special characters, except %, *
            file_name = re.sub(r'\s+', ' ', file_name).strip()  # Remove extra whitespace

            # Use multiple regex patterns to extract artist and album
            patterns = [
                r'^(.*?)\s*[-–—:]\s*(.*?)$',
                r'^(.*?)\s+by\s+(.*?)$',
            ]

            for pattern in patterns:
                match = re.match(pattern, file_name, re.IGNORECASE)
                if match:
                    artist, album = match.groups()
                    break
            else:
                # If no pattern matched, split on spaces and use the first part as artist and the rest as album
                parts = file_name.split(' ')
                if len(parts) >= 2:
                    artist, album = parts[0], ' '.join(parts[1:])
                else:
                    logging.warning(f"Failed to parse artist and album from filename: {file_name}")
                    continue

            # Remove any quotes around artist and album
            artist = re.sub(r'^\s*["\']|["\']$', '', artist)
            album = re.sub(r'^\s*["\']|["\']$', '', album)

            # Further clean up the parsed artist and album
            artist = re.sub(r'\(\d{4}\)', '', artist).strip()  # Remove year from artist
            album = re.sub(r'\(\d{4}\)', '', album).strip()  # Remove year from album
            album = re.sub(r'\(?(?:CD|Disc)\s*\d+\)?', '', album, flags=re.IGNORECASE).strip()  # Remove CD/Disc number

            # Call Discogs API to get the most accurate title and year
            try:
                title, year = call_discogs(artist.strip(), album.strip())
            except Exception as e:
                logging.error(f"Error calling Discogs API for {artist} - {album}: {str(e)}")
                title, year = None, None

            if title:
                # Compare the parsed artist and album with the API results
                artist_similarity = string_similarity(artist, title.split(' - ')[0])
                album_similarity = string_similarity(album, title.split(' - ')[-1])

                if artist_similarity > confidence_threshold and album_similarity > confidence_threshold:
                    # Use the API results if they're above the confidence threshold
                    artist, album = title.split(' - ')
                else:
                    # If the similarity is below the threshold, prompt the user for approval
                    print(f"Discogs API returned '{title}' for '{file_name}'")
                    user_input = input("Do you want to use the Discogs result? (y/n): ")
                    if user_input.lower() == 'y':
                        artist, album = title.split(' - ')
                    else:
                        logging.info(f"User chose to keep the original artist and album for {file_name}")
            else:
                logging.warning(f"No Discogs API results found for {artist} - {album}, using parsed values")

            # Prompt the user for approval of the cleaned artist and album
            print(f"Cleaned artist and album: '{artist}' - '{album}'")
            user_input = input("Do you want to use the cleaned artist and album? (y/n): ")
            if user_input.lower() != 'y':
                artist = input("Enter the correct artist name: ")
                album = input("Enter the correct album name: ")

            new_file_name = f"{artist} - {album}.mp3"
            new_path = os.path.join(folder_path, new_file_name)

            # Check if the new filename is the same as the old one (ignoring case and special characters)
            if re.sub(r'[^a-zA-Z0-9\s]', '', new_file_name.lower()) == re.sub(r'[^a-zA-Z0-9\s]', '', file_name.lower()):
                logging.info(f'Skipping rename for "{original_path}", filename is already correct')
            elif new_path != original_path:
                os.rename(original_path, new_path)
                logging.info(f'Renamed "{original_path}" to "{new_path}"')

            update_metadata(new_path, artist, album, year)

            processed_files[file_name] = {
                'original_path': original_path,
                'new_path': new_path,
                'artist': artist,
                'album': album,
                'year': year,
                'timestamp': file_timestamp
            }
            save_processed_files(processed_files)

def update_metadata(file_path, artist, album, year):
    try:
        audio = EasyID3(file_path)
        audio['artist'] = artist
        audio['album'] = album
        if year and year != 'Unknown Year':
            audio['date'] = [year]
        audio.save()
        logging.info(f"Updated metadata for {file_path}")
    except Exception as e:
        logging.error(f"Failed to update metadata for {file_path}: {str(e)}")


if __name__ == "__main__":
    music_folder = os.path.expanduser('~/desktop/production/Music Collection/Crate Holding Area')
    process_files(music_folder)