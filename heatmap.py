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
    def __init__(self, lat_bins=None, lon_bins=None, center=None, box_width=2, grid_res=0.001):
        """
        Initialize the heatmap class and the latitude and longitude bins. 

        Parameters
        ----------
        lat_bins : float array, optional
            Latitude histogram bins. Becomes class attribute.
        lon_bins : float array, optional
            Longitude histogram bins. Becomes class attribute.
        center : float list of len(2), optional
            The center of the map in the [lon, lat] format with
            negative West longitudes.
        box_width : float
            The size of the lat/lon box centered on center if 
            lat_bins or lon_bins are not specified.
        grid_res : float
            The resolution of the grid in degrees. Useful if the
            lat_bins or lon_bins kwargs are not specified.

        Example
        -------
        h = Heatmap(center=[-111.0329, 45.660])
        # Instead of running make_heatmap_hist() you can run 
        # h.load_heatmap() to load an existing ./data/heatmap.csv
        # file. 
        h.make_heatmap_hist() 
        h.make_map()

        Returns
        -------
        None     
        """
        self.grid_res = grid_res
        if (lat_bins is None) or (lon_bins is None):
            # If the user did not specify lat/lon bins assume were in Bozeman.
            self.center = [-111.0329, 45.660]
            # self.lon_bins = np.linspace(self.center[0]-box_width/2, self.center[0]+box_width/2,
            #                             num=self.grid_res)
            # self.lat_bins = np.linspace(self.center[1]-box_width/2, self.center[1]+box_width/2, 
            #                             num=self.grid_res)

            self.lon_bins = np.arange(self.center[0]-box_width/2, self.center[0]+box_width/2,
                                        grid_res)
            self.lat_bins = np.arange(self.center[1]-box_width/2, self.center[1]+box_width/2, 
                                        grid_res)
        else:
            self.lon_bins = lon_bins
            self.lat_bins = lat_bins
            self.center = center

        if not os.path.exists('./data/'):
            os.makedirs('./data/')
            print('Made empty data directory.')
        return

    def make_heatmap_hist(self, gpx_path='./data/', save_heatmap=True, verbose=False, gpx_pattern='*gpx'):
        """
        Makes a 2d lat-lon histogram using the gpx tracks in ./data. The gpx_pattern kwarg allows you to
        change the glob pattern e.g. wildcard (*) to match specific gpx files.

        Parameters
        ----------
        gpx_path : str, optional
            Path to gpx tracks, defaults to ./data/.
        save_heatmap : bool, optional
            Save the 2d histogram - wrapped in a Pandas DataFrame - to a file ./data/heatmap.csv
        verbose : bool, optional
            If true, will print gpx files that could not be processed, typically are treadmill 
            runs. This is useful for debugging if the heatmap is not generated.
        gpx_pattern : str, optional
            A pattern string that gets passed to glob.glob(). By default it will match all
            .gpx files.

        Returns
        -------
        self.heatmap : a Pandas DataFrame object containing the 2d histogram
            with the latitude bins in the index and longitude bins in the
            columns
        """
        # Get the names of gpx files in the ./data/ folder.
        self._get_gpx_files(gpx_path, gpx_pattern=gpx_pattern)

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
        return self.heatmap
    
    def make_map(self, map_zoom_start=11, heatmap_max_zoom=13, heatmap_radius=15, 
                heatmap_blur=15, heatmap_min_opacity=0.5):
        """ 
        Make a heatmap html file using folium

        Parameters
        ----------
        map_zoom_start : int, optional
            Passed into folium.plugins.HeatMap and folium.Map. Sets the start
            zoom level, the larger values will make a more zoomed-in map.
        heatmap_max_zoom
            Passed into folium.plugins.HeatMap and folium.Map to set the max zoom
            level.
        heatmap_radius : int, optional 
            Passed into folium.plugins.HeatMap to determine how large the heatmap
            blobs are.
        heatmap_blur : float, optional
            Passed into folium.plugins.HeatMap and sets the amount of bluring.
        heatmap_min_opacity : float, optional
            Passed into folium.plugins.HeatMap and sets the minimum opacity of the
            heatmap.

        Returns
        -------
        self.map : a folium map object with the heatmap layer.
        """
        if not hasattr(self, 'heatmap'):
            raise AttributeError('self.heatmap not found. Either run'
                                ' the make_heatmap_hist() or '
                                'load_heatmap() methods.')
        # Make a terrain map.
        self.map = folium.Map(location=self.center[::-1],
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
        self.map.add_child(heatmap)
        self.map.save('./data/heatmap.html')
        return self.map    

    def load_heatmap(self, heatmap_path='./data/heatmap.csv'):
        """ 
        Load the heatmap file into a Pandas DataFrame.

        Parameters
        ----------
        heatmap_path : str, optional
            The relative path to the heatmap.csv file.

        Returns
        -------
        None, creates self.heatmap attribute.
        """
        self.heatmap = pd.read_csv(heatmap_path, index_col=0)
        return


    def _get_gpx_files(self, gpx_path, gpx_pattern='.gpx'):
        """
        Get a list of paths to all gpx files.

        Parameters
        ----------
        gpx_path: str
            The path to the gpx data.
            
        gpx_pattern : str, optional
            The patten for glob.glob(). Can be useful for 
            filtering activity types.

        Returns
        -------
        None, creates self.gpx_files attribute.
        """
        self.gpx_files = glob.glob(
            os.path.join(gpx_path, gpx_pattern)
            )
        return
    
    def _save_heatmap(self, save_path='./data/heatmap.csv'):
        """
        Saves the heatmap to a csv file with the latitude bins saved as the 
        index and longitude bins saved as the columns.

        Parameters
        ----------
        save_path: str, optional
            The path where to save the heatmap.csv file.

        Returns
        -------
        None
        """
        self.heatmap.to_csv(save_path)
        return

if __name__ == '__main__':
    h = Heatmap()
    h.make_heatmap_hist()
    h.load_heatmap()
    h.make_map()