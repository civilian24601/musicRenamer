# Music Renaming Script

This script is designed to automate the process of renaming and tagging audio files, using the Discogs API to assist in naming validation. It cleans up the filenames, extracts artist and album information, and updates the metadata of the audio files.

## Prerequisites

- Python 3.x
- Required libraries: `requests`, `mutagen`, `python-dotenv`, `python-Levenshtein`

## Setup

1. Clone this repository or download the `renamer.py` script.

2. Install the required libraries by running the following command:

pip install requests mutagen python-dotenv python-Levenshtein

3. Obtain a Discogs API token:
- Sign up for a Discogs account if you don't have one already.
- Go to the Discogs Developer Settings page: https://www.discogs.com/settings/developers
- Create a new application and obtain the API token.

4. Create a `.env` file in the same directory as the script and add your Discogs API token:

DISCOGS_ACCESS_TOKEN=your_api_token_here

## Usage

1. Place the audio files you want to process in a directory.

2. Open a terminal or command prompt and navigate to the directory containing the `renamer.py` script.

3. Run the script using the following command:

python renamer.py

4. The script will process each audio file in the specified directory, cleaning up the filenames and retrieving metadata from the Discogs API.

5. If the confidence level of the retrieved metadata is below the threshold, the script will prompt you to manually approve or provide the correct artist and album information.

6. The script will rename the audio files based on the cleaned-up artist and album names and update the metadata accordingly.

7. Processed files will be skipped in subsequent runs unless they have been modified.

## Customization

- You can adjust the `confidence_threshold` parameter in the `process_files()` function to control the level of automation. A higher threshold will result in more manual intervention, while a lower threshold will allow more files to be processed automatically.

- The script uses a JSON file (`processed_files.json`) to keep track of processed files. You can modify the file path or use a different storage mechanism if needed.

## Contributing

If you encounter any issues or have suggestions for improvements, please feel free to open an issue or submit a pull request on the GitHub repository. This suits a niche use case for me, and I hope it can be useful to others as well in the cleaning and preprocessing of audio data collections.

## License

This script is released under the [MIT License](https://opensource.org/licenses/MIT).




