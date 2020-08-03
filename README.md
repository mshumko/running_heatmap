# running_heatmap
If you are curious on how to implement Strava's simple, yet rich [heatmap](https://www.strava.com/heatmap), this repository will help you get started. I show a straight-forward implementation of a heatmap using your own running tracks in gpx format which is inspired by ```geo-heatmap```. 

An example showing various running routes around Bozeman, Montana (the output html code is interactive)
<img src="https://github.com/mshumko/running_heatmap/blob/master/images/heatmap.png" alt="drawing" width="100%"/>
<!-- ![Bozeman area heatmap](https://github.com/mshumko/running_heatmap/blob/master/images/heatmap.png =250x) -->


## Steps to make your own heatmap
1. The two essential libraries are gpxpy for processing your gpx files; and folium, a wrapper for the Leaflet.js Javascript library. You can install these two libraries along with the standard numpy, pandas, etc. libraries with

```sudo pip3 install -r requirements.txt ```

2. Download the gpx files that you want to map and save them in the ```running_heatmap/data/``` folder (make a new folder the first time). You can get the data from Strava, but extra data manipulation is necessary. Alternatively, Garmin can provide you with all of your gpx files. Garmin Connect only allows you to manually download one track at a time, but it can be automated with the [garmin-connext-export](https://github.com/pe-st/garmin-connect-export) script. 

   *NOTE:* After Garmin Connect's July 2020 outage, I found that the ```garmin-connext-export``` no longer works so I now use the ```garminconnect``` library and with the ```download_activities.py``` wrapper script to download ```n``` most recent activities. This script is very simple and does not overwrite the old files in ```./data/```.

1. After you have the gpx data, you will make the heatmap with ```heatmap.py``` which will generate and save a 2d latitude-longitude heat histogram to ```./data/heatmap.csv``` and use it to make a heatmap saved in ```./data/heatmap.html```. On the backend the histogram is implemented using a List of Lists (LIL) sparse matrix format which allows the user to specify an arbitrarily dense latitude-longitude grid. Be aware that a high resolution world grid is slow to process because the binning takes a long time. 

   - Initialize the ```Heatmap``` object with the ```center``` kwarg that specifies the map center, well as the ```lat_bins``` and ```lon_bins``` that define the 2d heat histogram. If you don't specify these parameters the program assumes you live in Bozeman, and if you set ```global_grid=True``` the grid will be extended to the whole Earth (and the program takes much longer to process the gpx files). 
   - Histogram all of the gpx track files in ```running_heatmap/data/``` using the ```make_heatmap_hist()``` method. Optionally you can set the ```save_heatmap``` (true by default) kwarg to save the data to a csv file, to avoid the time consuming gpx track every time.
   - Use the 2d histogram and folium to make a heatmap with the ```make_map()``` method. This will generate a ```heatmap.html``` file in the data directory.
   - Drag the html file into a browser to explore the map. These are many useful kwargs to pass to the ```make_map()``` method to customize the heatmap to your liking.

Example:
```python
h = Heatmap(center=[-111.0329, 45.660])
h.make_heatmap_hist() # Run h.load_heatmap() instead if heatmap.csv is generated. 
h.make_map()
```