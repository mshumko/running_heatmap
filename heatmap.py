# This program makes a heatmap (plt.pcolormesh)
# of a bounded lat/lon area.

import glob
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker
import pandas as pd
import os

import gpxpy
import gpxpy.gpx

class Heatmap:
    def __init__(self, lat_bins=None, lon_bins=None, box_width=0.4):
        """ 
        Initialize the heatmap class and the latitude and longitude bins. 
        """
        self.grid_res = 200
        if (lat_bins is None) or (lon_bins is None):
            center = [-111.0329, 45.660]
            self.lon_bins = np.linspace(center[0]-box_width/2, center[0]+box_width/2,
                                        num=self.grid_res)
            self.lat_bins = np.linspace(center[1]-box_width/2, center[1]+box_width/2, 
                                        num=self.grid_res)
        else:
            self.lon_bins = lon_bins
            self.lat_bins = lat_bins
        return
    
    def make_map(self):
        """ 
        Make a heatmap i.e. a pcolormesh 
        """
        if not hasattr(self, 'heatmap'):
            raise AttributeError('self.heatmap not found. Either run'
                                ' the make_heatmap_hist() or '
                                'load_heatmap() methods.')
        _, self.ax = plt.subplots(figsize=(6,6))
        p = self.ax.pcolormesh(self.heatmap.columns, self.heatmap.index, self.heatmap.T, 
                            cmap='hot', shading='gouraud', vmax=200)

        self.ax.xaxis.set_visible(False)
        self.ax.yaxis.set_visible(False)
        plt.show()
        return

    def make_heatmap_hist(self, gpx_path='./data/', save_heatmap=True):
        """
        Loop over all the days, and take each track and 
        histrogram2d it.
        """
        self._get_gpx_files(gpx_path)
        heatmap = np.zeros((len(self.lon_bins)-1, len(self.lat_bins)-1))

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
    #h.make_heatmap_hist()
    h.load_heatmap()
    h.make_map()