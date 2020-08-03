import time
import argparse
import getpass
import pathlib
import numpy as np

import progressbar
import garminconnect

# Get the user info.
print('Welcome to the Garmin Connect gpx activity downloader')
username = input('username: ')
password = getpass.getpass("password: ")
download_num = int(input('Number of activities to download (if all use -1): '))

OVERWRITE = False

# 2000 activities is enough for me, but may not be for you. Adjust as necessary.
if download_num == -1:
    download_num = 2000

# Login to Garmin Connect and get a list of activity dictionaries.
client = garminconnect.Garmin(username, password)
client.login()
activities = client.get_activities(0, download_num)

# Make the save directory if one does not exist.
save_dir = pathlib.Path('./data/')
if not save_dir.exists():
    save_dir.mkdir()

# Remove the activities that have already been downloaded to ./data/
if not OVERWRITE:
    activity_paths = [save_dir / f'activity_{str(activity["activityId"])}.gpx' 
                        for activity in activities]
    activity_exists = np.array([activity_path.exists() 
                        for activity_path in activity_paths])
    activities = np.array(activities)[np.where(~activity_exists)[0]]

print(f'Downloading {len(activities)} activity files')

for activity in progressbar.progressbar(activities):
    activity_id = activity["activityId"]

    # Download the data.
    try:
        gpx_data = client.download_activity(activity_id, dl_fmt=client.ActivityDownloadFormat.GPX)
    except (garminconnect.GarminConnectConnectionError,
            garminconnect.GarminConnectAuthenticationError,
            garminconnect.GarminConnectTooManyRequestsError) as err:
        print(f'Unable to download {activity_id} because: {str(err)}')
        continue

    # Save the data
    save_path = save_dir / f'activity_{str(activity_id)}.gpx'
    with open(save_path, "wb") as fb:
        fb.write(gpx_data)

    # To be nice to Garmin's server. Technically it is not necessary since Garmin.com's 
    # robot.txt file does not specifically specify a hit rate.
    time.sleep(1) 