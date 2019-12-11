# This program makes a heatmap (plt.pcolormesh)
# of a bounded lat/lon area.

import glob
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import os

import gpxpy
import gpxpy.gpx

class Heatmap:
    def __init__(self, lat_bins=None, lon_bins=None, box_width=0.1):
        """ 
        Initialize the heatmap class and the latitude and longitude bins. 
        """
        if (lat_bins is None) or (lon_bins is None):
            center = [-111.0429, 45.660]
            self.lon_bins = np.linspace(center[0]-box_width/2, center[0]+box_width/2,
                                        num=100)
            self.lat_bins = np.linspace(center[1]-box_width/2, center[1]+box_width/2, 
                                        num=100)
        else:
            self.lon_bins = lon_bins
            self.lat_bins = lat_bins
        return
    
    def make_map(self):
        """ 
        Make a heatmap i.e. a pcolormesh 
        """
        p = plt.pcolormesh(self.lon_bins, self.lat_bins, self.heatmap.T, cmap='hot')
        plt.colorbar(p)
        plt.show()
        return

    def make_heatmap_hist(self, gpx_path='./data/'):
        """
        Loop over all the days, and take each track and 
        histrogram2d it.
        """
        self._get_gpx_files(gpx_path)
        self.heatmap = np.zeros((len(self.lon_bins)-1, len(self.lat_bins)-1))

        for gpx_file in self.gpx_files:
            with open(gpx_file) as f:
                try:
                    gpx = gpxpy.parse(f)
                except gpxpy.gpx.GPXXMLSyntaxException as err:
                    if 'Error parsing XML: no element found:' in str(err):
                        print(f'No element file in {gpx_file}. Empty file?')
                        continue

                for track in gpx.tracks:
                    for segment in track.segments:
                        lons = [i.longitude for i in segment.points]
                        lats = [i.latitude for i in segment.points]
                        H, _, _ = np.histogram2d(lons, lats,  
                                                bins=(
                                                    self.lon_bins, self.lat_bins
                                                ))
                        self.heatmap += H
        return                 

    def _get_gpx_files(self, gpx_path):
        """
        Get a list of paths to all gpx files.
        """
        self.gpx_files = glob.glob(
            os.path.join(gpx_path, '*Running*gpx')
            )
        return

if __name__ == '__main__':
    h = Heatmap()
    h.make_heatmap_hist()
    h.make_map()