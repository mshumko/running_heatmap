# This script loads in all of the gpx files in the ./data/ folder
# and saves each run's mid point position to a new gpx file.

import glob

import gpxpy
import gpxpy.gpx

out_filename = 'waypoints.gpx'

# Find all of the gpx files in the data/directory.
gpx_files = glob.glob('./data/*Running*gpx')
output_file = gpxpy.gpx.GPX()

# What gps point to use. Options are 'first', 'mid', or 'random'.
use_point = 'mid'

# Loop over the gpx files in ./data/
for gpx_file in gpx_files:
    # open and parse the gpx file.
    with open(gpx_file) as f:
        try:
            gpx = gpxpy.parse(f)
        except gpxpy.gpx.GPXXMLSyntaxException as err:
            if 'Error parsing XML: no element found:' in str(err):
                print(f'No element file in {gpx_file}. Empty file?')
                continue
    
        for track in gpx.tracks:
            for segment in track.segments:

                if use_point == 'mid': 
                    n = len(segment.points)//2
                elif use_point == 'first': 
                    n = 0
                elif use_point == 'random': 
                    n = np.random.randint(len(segment.points))
                else: 
                    raise ValueError('Incorrect use_point specified. '
                                     'Try "mid", "first", or "random"')
                
                # Append the one segment point to the output file.
                output_file.waypoints.append(
                    gpxpy.gpx.GPXWaypoint(
                    latitude=segment.points[n].latitude,
                    longitude=segment.points[n].longitude, 
                    elevation=segment.points[n].elevation
                    ))                    

with open(out_filename, 'w') as f:
     for row in output_file.to_xml():
        f.write(row)
