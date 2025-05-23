from pymediainfo import MediaInfo
from CONFIG import *
import os
import shutil
import utils as u
import db
from pathlib import Path
from utils import coloured_print as cprint
from research_utils import significant_beginning


def convert_milliseconds(milliseconds):
    # Calculate total seconds
    total_seconds = milliseconds // 1000

    # Calculate hours, minutes, and seconds
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return hours, minutes, seconds


# return duration as (hours, minutes, seconds), languages and subtitles as a list of the available ones.
def extract_video_metadata(file_path, test=False):
    media_info = MediaInfo.parse(file_path)
    duration = None
    languages = []
    subtitles = []

    for track in media_info.tracks:
        if track.track_type == "General":
            if track.duration == None:
                duration = "Unknown"
            else:
                duration = convert_milliseconds(int(float(track.duration)))
                duration = (
                    str(duration[0])
                    + " h "
                    + str(duration[1])
                    + " m "
                    + str(duration[2])
                    + " s "
                )
        elif track.track_type == "Audio":
            if track.other_language == None:
                languages.append("Piste " + str(len(languages) + 1))
            else:
                languages.append(track.other_language[0])
        elif track.track_type == "Text":
            if track.other_language == None:
                subtitles.append("Piste " + str(len(subtitles) + 1))
            else:
                subtitles.append(track.other_language[0])

    if test:
        print(f"Duration: {duration}")
        print(f"audio : {languages}")
        print(f"subtitles : {subtitles}")

    return duration, languages, subtitles


def text_formatter(text, test=False):
    punc_sep = u.punctuation_split(text)
    extension = punc_sep.pop()
    formatted_text = " ".join(punc_sep)
    formatted_text += "." + extension
    # First letter in capital
    formatted_text = formatted_text[0].upper() + formatted_text[1:].lower()
    if test:
        print(formatted_text)
    return formatted_text


def move_and_rename_file(source_path, destination_path, test=False):
    try:
        # Move and rename the file

        shutil.move(source_path, destination_path)
        if test:
            print(
                f"File moved and renamed successfully from {source_path} to {destination_path}"
            )
    except FileNotFoundError:
        print(f"Error: The file {source_path} does not exist.")
    except PermissionError:
        print(f"Error: Permission denied when trying to move {source_path}.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def create_folder(folder_path, test=False):
    try:  # if os.path.isfile(file_path):
        # Create the directory
        if os.path.isdir(folder_path):
            print(f"Folder {folder_path} already existed")
        else:
            os.makedirs(folder_path, exist_ok=True)
            if test:
                print(f"Folder created successfully at {folder_path}")

    except Exception as e:
        print(f"An error occurred while creating the folder: {e}")


def remove_empty_folder(folder_path, test=False):
    try:
        if os.path.isdir(folder_path):
            os.rmdir(folder_path)
            if test:
                print(f"Empty folder deleted successfully at {folder_path}")
        else:
            print(f"Folder {folder_path} doesn't exist")

    except OSError as e:
        print(f"Error: {folder_path} : {e.strerror}")


# From a set of languages et subtitles, bool : is it vost and not french ?
# Arguments should be lists
def is_vost(languages, subtitles):
    return len(list(set(languages))) >= 2 and len(subtitles) >= 1


def is_video(file_path):
    return u.get_extension(file_path).lower() in POSSIBLE_EXTENSIONS and os.path.isfile(
        file_path
    )


def is_film(file_path):
    video = is_video(file_path)
    if not video:
        return False
    else:
        media_info = MediaInfo.parse(file_path)
        for track in media_info.tracks:
            if track.track_type == "General":
                if track.duration == None:
                    duration = (0, 0, 0)
                else:
                    duration = convert_milliseconds(int(float(track.duration)))
    return duration > (0, 30, 0)


# Exception if it's not a film.
# Register the film row in the database
# Returns the old and new name
# Doesn't register films that already are there
def register(film_path, disk_number):
    assert is_film(film_path), "you tried to register a file that is not a film."

    duration, languages, subtitles = extract_video_metadata(film_path)

    film_path = Path(film_path)

    old_film_title = film_path.name
    new_film_title = text_formatter(old_film_title)
    vost = is_vost(languages, subtitles)

    row = [
        new_film_title,
        disk_number,
        duration,
        vost,
        ", ".join(languages),
        ", ".join(subtitles),
        old_film_title
    ]
    row = [[row[i], COLUMNS[i][1]] for i in range(len(row))]
    if not db.is_in_table(DB_NAME, TABLE_NAME, COLUMNS, new_film_title):
        db.add_row(DB_NAME, TABLE_NAME, COLUMNS, row)
    else:
        other_film = db.get_row(DB_NAME, TABLE_NAME, COLUMNS, new_film_title)
        other_film_disk = other_film.Disk_number
        double_name = "Disk " + disk_number + " : " + new_film_title
        if other_film_disk != disk_number and not db.is_in_table(DB_NAME, TABLE_NAME, COLUMNS, double_name):
            row[0][0] = double_name
            db.add_row(DB_NAME, TABLE_NAME, COLUMNS, row)

    return old_film_title, new_film_title


# This function treats files when there's no group effect.
# It means that
# It :
# Puts in Other if file and not film .
# Puts at the root and rename the file name if it's a film
# and registers its information in the db if it's a film.
# If it is a folder, it also moves it in Other

# It only works ON FILES AND in the following cases :
# - the file is a film
# - the folder contains some films.
# No test of valid using for the


def simple_treater(file_path, disk_number):
    if is_film(file_path):
        _, new_film_title = register(file_path, disk_number)
        move_and_rename_file(file_path, Path(DISK_LOCATION) / new_film_title)
    elif file_path.name != "Other":
        file_title = Path(file_path).name  # Works also on folders
        move_and_rename_file(file_path, Path(DISK_LOCATION) / "Other" / file_title)


if __name__ == "__main__":
    # Example usage
    file_path = "C:\\colin_films\\Dersou.Ouzala\\Dersou.Ouzala.mkv"
    extract_video_metadata(file_path, test=True)
    test_str = "Hello I'm COLIN. DROUINEAU 1253.MIDJ .mkv"
    text_formatter(test_str, test=True)
