import os
import glob
import psycopg2
import pandas as pd
from sql_queries import *
import datetime as dt


def insert_record(cur, insert_query, df, fields):
    """
    Insert a record into a DB table.
    :param cur: connection cursor to insert the data in DB.
    :param insert_query: query SQL for Insert.
    :param df: dataframe with the record.
    :param fields: array of fields of the data to insert.
    """
    # df[fields].values is still a df, and df[fields].values[0] is a numpy array, need to convert it to list of string for query
    record = df[fields].values[0].tolist()
    cur.execute(insert_query, record)

def insert_dataframe(cur, df, insert_query):
    """
    Insert a pandas dataframe into a DB table
    :param cur: connection cursor to insert the data in DB.
    :param df: dataframe with the record.
    :param insert_query: query SQL for Insert.
    """
#     print("new way to insert df")
    for i, row in df.iterrows():
        cur.execute(insert_query, list(row)) # convert row values to list for query

def process_song_file(cur, filepath):
    """
    Process the songs files and insert data into dimension tables: songs and artists.
    :param cur: connection cursor to insert the data in DB.
    :param filepath: path/to/the/song/file.
    """
    
    # open song file
    df = pd.read_json(filepath, lines=True)
    
    # insert song record
    song_fields = ['song_id', 'title', 'artist_id', 'year', 'duration']
    insert_record(cur, song_table_insert, df, song_fields)
                  
    # insert artist record
    artist_fields = ['artist_id', 'artist_name', 'artist_location', 'artist_latitude', 'artist_longitude']
    insert_record(cur, artist_table_insert, df, artist_fields)

def expand_time_data(df, ts_field):
    """
    Add more time elements to a dataframe from a UNIX timestamp in milliseconds.
    :param df: pandas dataframe to add time fields.
    :param ts_field: name of the timestamp field field.
    :return: pandas dataframe with more time fields.
    """
    df['year'] = df[ts_field].dt.year
    df['month'] = df[ts_field].dt.month
    df['day'] = df[ts_field].dt.day
    df['hour'] = df[ts_field].dt.hour
    df['weekday_name'] = df[ts_field].dt.strftime('%A')
    df['week'] = df[ts_field].dt.isocalendar().week
    
    return df


def get_songid_artistid(cur, song, artist, length):
    """
    Gets the song_id and the artist_id from song tittle, artist name and song duration.
    :param cur: connection cursor to query the data in DB.
    :param song: song tittle
    :param artist: artist name
    :param length: song duration
    :return: returns song_id and artist_id
    """

    # get songid and artistid from song and artist tables
    cur.execute(song_select, (song, artist, length))
    
    results = cur.fetchone()
#     print(results)
    song_id, artist_id = results if results else None, None
    return song_id, artist_id

def insert_facts_songplays(cur, df):
    """
    Insert songplays fact table
    :param cur: connection cursor to insert the data in DB.
    :param df: dataframe with song plays data.
    """

    # insert songplay records
    for i, row in df.iterrows():
        songid, artistid = get_songid_artistid(cur, row['song'], row['artist'], row['length'])
        songplay_data = (row.ts, row.userId, row.level, songid, artistid,
                         row.itemInSession, row.location, row.userAgent)
        cur.execute(songplay_table_insert, songplay_data)


def process_log_file(cur, filepath):
    """
    Process the log files and insert data into dimension tables: time and users.
    Insert data into the facts table songplays.
    :param cur: connection cursor to insert the data in DB.
    :param filepath: path/to/the/log/file.
    """

    # open log file
    df = pd.read_json(filepath, lines=True)
    # filter by NextSong action
    df = df.loc[df['page'] == 'NextSong']
    # convert timestamp column to datetime
    df['datetime'] = pd.to_datetime(df['ts'], unit='ms')
    # insert time data records
    df = expand_time_data(df, 'datetime')
    time_data = df[['ts', 'hour', 'day', 'week', 'month', 'year', 'weekday_name']]
    insert_dataframe(cur, time_data, time_table_insert)
    # load user table
    user_df = df[['userId', 'firstName', 'lastName', 'gender', 'level']]
    # insert user records
    insert_dataframe(cur, user_df, user_table_insert)
    # insert songplay records     
    insert_facts_songplays(cur, df)
    
def get_all_files_matching_from_directory(directorypath, match):
    """
    Get all the files that match into a directory recursively.
    :param directorypath: path/to/directory.
    :param match: match expression.
    :return: array with all the files that match.
    """
    # get all files matching extension from directory
    all_files = []
    for root, dirs, files in os.walk(directorypath):
        files = glob.glob(os.path.join(root, match))
        for f in files:
            all_files.append(os.path.abspath(f))
    return all_files

def process_data(cur, conn, filepath, func):
    """
    Process all the data, either songs files or logs files
    :param cur: connection cursor to insert the data in DB.
    :param conn: connection to the database to do the commit.
    :param filepath: path/to/data/type/directory
    :param func: function to process, transform and insert into DB the data.
    """
    # get total number of files found
    all_files = get_all_files_matching_from_directory(filepath, '*.json')
    print('There are total %s files found in %s' % (str(len(all_files)), filepath))
   
    # iterate over files and process
#     conn.
    for i, f in enumerate(all_files, 1):
        func(cur, f)
        conn.commit()
        print('{}/{} files have been processed.'.format(i, len(all_files)))
                           
def main():
    #conn = psycopg2.connect("host=127.0.0.1 dbname=sparkifydb user=student password=student")
    conn = psycopg2.connect("host=127.0.0.1 dbname=sparkifydb user=postgres password=123456")
#     conn.set_session(autocommit=True)
    cur = conn.cursor()

    process_data(cur, conn, filepath='data/song_data', func=process_song_file)
    process_data(cur, conn, filepath='data/log_data', func=process_log_file)

    conn.close()


if __name__ == "__main__":
    main()