# running_heatmap

This project replicates Strava's [heat map](www.strava.com/heatmap) and plots my runs in and around Bozeman. The heatmap is generated with the following steps:

1. Install the gpxpy, folium, and pandas using 

```sudo pip3 install -r requirements.txt ```

2. Obtain your gpx files that you want to map and place the gpx files in the /data/ folder in the base repo directory. Strava can export data but data manipulation is necessary. It is super easy to export data from Garmin via [garmin-connext-export](https://github.com/pe-st/garmin-connect-export).

3. Run heatmap.py to generate a heatmap file in ./data/heatmap.csv and heatmap.html

    Example:
    ```python
    h = Heatmap()
    h.make_heatmap_hist() # No need to run this if heatmap.csv is already generated. Run h.load_heatmap()
    h.make_map()
    ```

    Open heatmap.html in your browser and enjoy.