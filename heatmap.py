import numpy as np
import matplotlib.pyplot as plt
import scipy.sparse # To make a sparse lat/lon matrix
import pandas as pd
import pathlib

import progressbar
import folium
import folium.plugins
import gpxpy
import gpxpy.gpx

class Heatmap:
    def __init__(self, lat_bins=None, lon_bins=None, center=None, 
            box_width=10, grid_res=0.001, global_grid=False):
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
        global_grid : bool
            If lat/lon bins are not specied, setting this kwarg will
            make a global lat/lon grid for your activities. This 
            greatly slows down the data processing due to the size of 
            the arrays, even with sparse matrices. 

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
            # If the user did not specify lat/lon bins assume we live in Bozeman.
            self.center = [-111.0329, 45.660]

            if global_grid:
                self.lon_bins = np.arange(-180, 180, grid_res)
                self.lat_bins = np.arange(-90, 90, grid_res)
            else:
                self.lon_bins = np.arange(self.center[0]-box_width/2, self.center[0]+box_width/2,
                                            grid_res)
                self.lat_bins = np.arange(self.center[1]-box_width/2, self.center[1]+box_width/2, 
                                            grid_res)
        else:
            self.lon_bins = lon_bins
            self.lat_bins = lat_bins
            self.center = center

        if not pathlib.Path('./data/').exists():
            pathlib.Path('./data/').mkdir()
            print('Made empty data directory.')
        return

    def make_heatmap_hist(self, gpx_path='./data/', save_heatmap=True, 
                        verbose=False, gpx_pattern='*gpx'):
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
        self._get_gpx_files(gpx_path, gpx_pattern)

        # 2d heatmap histrogram.
        self.heatmap = scipy.sparse.lil_matrix(
                    (len(self.lon_bins), len(self.lat_bins)), dtype='uint'
                    )

        for gpx_file in progressbar.progressbar(self.gpx_files):
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
                        # list of longitude coordinates
                        lons = np.array([i.longitude for i in segment.points])
                        # list of latitude coordinates 
                        lats = np.array([i.latitude for i in segment.points])
                        # For each gpx point find the closest grid point in
                        # self.lon_bins and self.lat_bins
                        idx = self._get_closest_index(lons, lats)
                        for lon_i, lat_i in idx:
                            # Note: the += notation is not supported yet by scipy.sparse
                            self.heatmap[lon_i, lat_i] = self.heatmap[lon_i, lat_i] + 1

        if save_heatmap: self._save_heatmap()
        return self.heatmap
    
    def make_map(self, map_zoom_start=11, heatmap_max_zoom=13, heatmap_radius=10, 
                heatmap_blur=15, heatmap_min_opacity=0.7):
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

        # If the heatmap is in a DataFrame or sparse matrix format, convert 
        # to an array of (N-Non-Zero-Bins)*3. Columns are lon, lat, heat.
        if isinstance(self.heatmap, scipy.sparse.lil_matrix):
            heat_list = self._convert_sparse_to_lists(self.heatmap)
        elif isinstance(self.heatmap, pd.DataFrame):
            heat_list = self.heatmap.values
        # Swap the columns to be in the lat, lon, heat order
        data = heat_list[:, [1, 0, 2]]

        # Make a terrain map.
        self.map = folium.Map(location=self.center[::-1],
                       zoom_start=map_zoom_start,
                       tiles='Stamen Terrain', max_zoom=heatmap_max_zoom)
        # Make the heatmap.
        heatmap = folium.plugins.HeatMap(data,
                        max_val=data.max(),
                        min_opacity=heatmap_min_opacity,
                        radius=heatmap_radius,
                        blur=heatmap_blur,
                        max_zoom=heatmap_max_zoom)
        self.map.add_child(heatmap) # Add the heatmap to the map object.
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
        self.heatmap = pd.read_csv(heatmap_path)
        return

    def _get_gpx_files(self, gpx_path, gpx_pattern):
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
        self.gpx_files = list(pathlib.Path(gpx_path).glob(gpx_pattern))
        print(f'{__file__}: Found {len(self.gpx_files)} gpx files')
        return

    def _get_closest_index(self, lons, lats):
        """
        Given a longitude and latitude lists, calculate the closet index in 
        self.lat_bins and self.lon_bins point.

        Parameters
        ----------
        lons : ndarray
            A 1D array of longitude points
        lats : ndarray
            A 1D array of latitude points

        Returns
        -------
        idx : a len(lons)x2 ndarray that contanins the index of
            self.lon_grid and self.lat_grid points that are closest 
            to the lons and lats arrays.
        """
        assert len(lons) == len(lats), 'Longitude and latitude arrays must be the same shape.'

        idx = np.nan*np.ones((len(lons), 2), dtype=int)

        for i, (lon_i, lat_i) in enumerate(zip(lons, lats)):
            idx[i, 0] = np.argmin(np.abs(self.lon_bins - lon_i))
            idx[i, 1] = np.argmin(np.abs(self.lat_bins - lat_i))
        return idx

    def _save_heatmap(self, save_path='./data/heatmap.csv'):
        """
        Saves the heatmap to a csv file with the following three columns:
        lon, lat, heat.

        Parameters
        ----------
        save_path: str, optional
            The path where to save the csv file, by default the csv file
            is saved in './data/heatmap.csv'. 

        Returns
        -------
        None
        """
        non_zero_entries = self._convert_sparse_to_lists(self.heatmap)
        df = pd.DataFrame(data=non_zero_entries, columns=['lon', 'lat', 'heat'])
        df.to_csv(save_path, index=False)
        return

    def _convert_sparse_to_lists(self, x):
        """
        Converts the sparse matrix x into a three lists that contain only the 
        non-zero values: a longitude array, a latitude array, and a heat array. 

        Parameters
        ----------
        x: scipy.sparse.lil_matrix
            The sparse matrix object to convert.

        Returns
        -------
        non_zero_entries: ndarray
            An array with (N-Non-Zero-Bins)*3 dimensions. 
            The columns are lon, lat, heat.
        """
        if not isinstance(x, scipy.sparse.lil_matrix):
            raise ValueError('Heatmap is not in the LIL sparse matrix format.')
        coo_fmt = x.tocoo()

        non_zero_entries = np.nan*np.ones((len(x.nonzero()[0]), 3))
        non_zero_entries[:, 0] = self.lon_bins[coo_fmt.row]
        non_zero_entries[:, 1] = self.lat_bins[coo_fmt.col]
        non_zero_entries[:, 2] = coo_fmt.data
        return non_zero_entries

if __name__ == '__main__':
    h = Heatmap()
    # h.make_heatmap_hist()
    h.load_heatmap()
    h.make_map()