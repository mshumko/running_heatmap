# This program makes a heatmap (plt.pcolormesh)
# of a bounded lat/lon area.

import glob
import numpy as np
import matplotlib.pyplot as plt
import scipy.ndimage
import pandas as pd
import os

import folium
import folium.plugins
import gpxpy
import gpxpy.gpx

class Heatmap:
    def __init__(self, lat_bins=None, lon_bins=None, box_width=0.4, grid_res=500):
        """ 
        Initialize the heatmap class and the latitude and longitude bins. 
        """
        self.grid_res = grid_res
        if (lat_bins is None) or (lon_bins is None):
            # If the user did not specify lat/lon bins assume were in Bozeman.
            self.center = [-111.0329, 45.660]
            self.lon_bins = np.linspace(self.center[0]-box_width/2, self.center[0]+box_width/2,
                                        num=self.grid_res)
            self.lat_bins = np.linspace(self.center[1]-box_width/2, self.center[1]+box_width/2, 
                                        num=self.grid_res)
        else:
            self.lon_bins = lon_bins
            self.lat_bins = lat_bins

        if not os.path.exists('./data/'):
            os.makedirs('./data/')
            print('Made empty data directory.')
        return
    
    def make_map(self, blur_sigma=0.5, map_zoom_start=11, heatmap_radius=15,
                    heatmap_blur=15, heatmap_min_opacity=0.5,
                    heatmap_max_zoom=14):
        """ 
        Make a heatmap html file using folium
        """
        if not hasattr(self, 'heatmap'):
            raise AttributeError('self.heatmap not found. Either run'
                                ' the make_heatmap_hist() or '
                                'load_heatmap() methods.')
        # Make a terrain map.
        self.m = folium.Map(location=self.center[::-1],
                       zoom_start=map_zoom_start,
                       tiles='Stamen Terrain', max_zoom=heatmap_max_zoom)

        # Overlay the heatmap
        latlat, lonlon = np.meshgrid(
                                    self.heatmap.index, 
                                    self.heatmap.columns.astype(float)
                                    )
        # idx boolean array necessary to not include lat-lon bins 
        # with 0 gpx points because you can see all those points
        # on the map.
        idx = np.where(self.heatmap.values)
        data = np.stack([latlat[idx].flatten(), 
                        lonlon[idx].flatten(), 
                        self.heatmap.values[idx].flatten()], 
                        axis=-1)
        # Add the heatmap with many argument tweaks.
        heatmap = folium.plugins.HeatMap(data,
                         max_val=self.heatmap.values.max(),
                          min_opacity=heatmap_min_opacity,
                          radius=heatmap_radius,
                          blur=heatmap_blur,
                          max_zoom=heatmap_max_zoom)
        self.m.add_child(heatmap)
        self.m.save('./data/heatmap.html')
        return

    def make_heatmap_hist(self, gpx_path='./data/', save_heatmap=True, verbose=False):
        """
        Loop over all the days, and take each track and 
        histrogram2d it.
        """
        # Get the names of gpx files in the ./data/ folder.
        self._get_gpx_files(gpx_path)

        # 2d heatmap histrogram.
        heatmap = np.zeros((len(self.lon_bins)-1, len(self.lat_bins)-1))

        for gpx_file in self.gpx_files:
            with open(gpx_file) as f:
                # Check for empty gpx files that are typically due to 
                # treadmill runs.
                try:
                    gpx = gpxpy.parse(f)
                except gpxpy.gpx.GPXXMLSyntaxException as err:
                    if 'Error parsing XML: no element found:' in str(err):
                        if verbose: print(f'No element file in {gpx_file}. Empty file?')
                        continue

                # Loop through each track. Each run file should only have one.
                for track in gpx.tracks:
                    # Loop over all of the track segments (time, lat, lon, alt) points.
                    for segment in track.segments:
                        # Histogram the lat-lon coordinates.
                        lons = [i.longitude for i in segment.points]
                        lats = [i.latitude for i in segment.points]
                        H, _, _ = np.histogram2d(lons, lats,  
                                                bins=(
                                                    self.lon_bins, self.lat_bins
                                                ))
                        heatmap += H
        self.heatmap = pd.DataFrame(data=heatmap, 
                                    index=self.lat_bins[:-1], 
                                    columns=self.lon_bins[:-1])
        if save_heatmap: self._save_heatmap()
        return            

    def load_heatmap(self, heatmap_path='./data/heatmap.csv'):
        """ Loads the heatmap file into a Pandas dataframe """
        self.heatmap = pd.read_csv(heatmap_path, index_col=0)
        return


    def _get_gpx_files(self, gpx_path):
        """
        Get a list of paths to all gpx files.
        """
        self.gpx_files = glob.glob(
            os.path.join(gpx_path, '*Running*gpx')
            )
        return
    
    def _save_heatmap(self, save_path='./data/heatmap.csv'):
        """
        Saves the heatmap to a csv file with the latitude bins saved as the 
        index and longitude bins saved as the columns
        """
        self.heatmap.to_csv(save_path)
        return

if __name__ == '__main__':
    h = Heatmap()
    h.make_heatmap_hist()
    h.load_heatmap()
    h.make_map()