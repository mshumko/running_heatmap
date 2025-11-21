import pathlib

import numpy as np
import matplotlib.pyplot as plt
import scipy.sparse # To make a sparse lat/lon matrix
import pandas as pd
import tqdm
import folium
import folium.plugins
import gpxpy
import gpxpy.gpx
import multiprocessing

def _closest_indices_vectorized(points, bins):
    """
    Vectorized nearest-index lookup using np.searchsorted.
    Returns an int array of indices into bins (same shape as points).
    """
    if len(points) == 0:
        return np.array([], dtype=int)
    idx = np.searchsorted(bins, points)
    idx_left = np.clip(idx - 1, 0, len(bins) - 1)
    idx_right = np.clip(idx, 0, len(bins) - 1)
    left_diff = np.abs(bins[idx_left] - points)
    right_diff = np.abs(bins[idx_right] - points)
    use_right = right_diff < left_diff
    return np.where(use_right, idx_right, idx_left).astype(int)

def _process_gpx_file(gpx_file, lon_bins, lat_bins, verbose=False):
    """
    Process one gpx file: parse lons/lats, compute closest grid indices,
    and return (rows, cols, data) arrays suitable for building a coo_matrix.
    """
    try:
        with open(gpx_file) as f:
            gpx = gpxpy.parse(f)
    except Exception as err:
        if verbose:
            print(f'Could not parse {gpx_file}: {err}')
        return (np.array([], dtype=int), np.array([], dtype=int), np.array([], dtype=np.uint32))

    all_lons = []
    all_lats = []
    for track in gpx.tracks:
        for segment in track.segments:
            if len(segment.points) == 0:
                continue
            lons = np.array([p.longitude for p in segment.points])
            lats = np.array([p.latitude for p in segment.points])
            all_lons.append(lons)
            all_lats.append(lats)

    if not all_lons:
        return (np.array([], dtype=int), np.array([], dtype=int), np.array([], dtype=np.uint32))

    lons = np.concatenate(all_lons)
    lats = np.concatenate(all_lats)

    lon_idx = _closest_indices_vectorized(lons, lon_bins)
    lat_idx = _closest_indices_vectorized(lats, lat_bins)

    rows = lon_idx.astype(int)
    cols = lat_idx.astype(int)
    data = np.ones(len(rows), dtype=np.uint32)
    return (rows, cols, data)

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
            self.center = [-77, 39]

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
                          verbose=False, gpx_pattern='*gpx', n_workers=1):
        """
        Parallelized: n_workers None -> os.cpu_count(), 1 -> sequential.
        Returns self.heatmap (scipy.sparse.lil_matrix).
        """
        # Get the names of gpx files in the ./data/ folder.
        self._get_gpx_files(gpx_path, gpx_pattern)

        nlon = len(self.lon_bins)
        nlat = len(self.lat_bins)

        if n_workers is None:
            n_workers = multiprocessing.cpu_count()

        # Sequential (single-process) fast path: reuse original loop logic but using helper.
        if n_workers == 1 or len(self.gpx_files) <= 1:
            # build rows/cols/data lists and then aggregate
            rows_list = []
            cols_list = []
            data_list = []
            for gpx_file in tqdm.tqdm(self.gpx_files):
                r, c, d = _process_gpx_file(str(gpx_file), self.lon_bins, self.lat_bins, verbose=verbose)
                if r.size:
                    rows_list.append(r)
                    cols_list.append(c)
                    data_list.append(d)
            if not rows_list:
                self.heatmap = scipy.sparse.lil_matrix((nlon, nlat), dtype='uint')
            else:
                rows = np.concatenate(rows_list)
                cols = np.concatenate(cols_list)
                data = np.concatenate(data_list)
                coo = scipy.sparse.coo_matrix((data, (rows, cols)), shape=(nlon, nlat), dtype='uint')
                # convert to LIL and sum duplicates by going through CSR
                self.heatmap = coo.tocsr().tolil()
        else:
            # Parallel path
            args = [(str(g), self.lon_bins, self.lat_bins, verbose) for g in self.gpx_files]
            with multiprocessing.Pool(processes=n_workers) as pool:
                results = list(tqdm.tqdm(pool.starmap(_process_gpx_file, args), total=len(args)))
            # aggregate results
            rows = np.concatenate([r for r, c, d in results if r.size]) if any(r.size for r, c, d in results) else np.array([], dtype=int)
            cols = np.concatenate([c for r, c, d in results if c.size]) if any(c.size for r, c, d in results) else np.array([], dtype=int)
            data = np.concatenate([d for r, c, d in results if d.size]) if any(d.size for r, c, d in results) else np.array([], dtype=np.uint32)

            if rows.size == 0:
                self.heatmap = scipy.sparse.lil_matrix((nlon, nlat), dtype='uint')
            else:
                coo = scipy.sparse.coo_matrix((data, (rows, cols)), shape=(nlon, nlat), dtype='uint')
                self.heatmap = coo.tocsr().tolil()

        if save_heatmap:
            self._save_heatmap()
        return self.heatmap
    
    def make_map(self, map_zoom_start=11, heatmap_max_zoom=13, heatmap_radius=10, 
                heatmap_blur=15, heatmap_min_opacity=0.7, saturation_percentile=100):
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
        saturation_percentile : float, optional
            Apply a mask that sets all values above the saturation_percentile 
            percentile (values 0 to 100) to the saturation_percentile's heat 
            value. This kwarg is useful to make it hard to identify where you 
            work, live, or your most popular running routes.

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

        if saturation_percentile < 100:
            # Apply the saturation percentile mask
            data[:, 2] = self._apply_percentile_mask(
                            data[:, 2], 
                            saturation_percentile
                            )

        # Make a terrain map.
        self.map = folium.Map(
            location=self.center[::-1],
            zoom_start=map_zoom_start,
            tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
            attr=(
                'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                ' contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy;'
                '<a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org'
                '/licenses/by-sa/3.0/">CC-BY-SA</a>)'
                ),
            max_zoom=heatmap_max_zoom
            )
        # Make the heatmap.
        heatmap = folium.plugins.HeatMap(data,
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
        return idx.astype(int)

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

    def _apply_percentile_mask(self, heat, percentile):
        """ 
        Applies a percentile saturation mask to the 1D heat array. Heat 
        values > percentile(heat) are set to percentile(heat)

        Parameters
        ----------
        heat : ndarray
            A 1D array of heat values.
        percentile : float
            The saturation percentile between 0 and 100.

        Returns
        -------
        heat : ndarray
            An array of the same shape as heat, except with values greater than
            percentile(heat) are set to percentile(heat).
        """
        saturation_heat = np.percentile(heat, percentile)
        heat[heat > saturation_heat] = saturation_heat
        return heat
    

if __name__ == '__main__':
    heat = Heatmap(global_grid=True, grid_res=0.0005)
    heat.make_heatmap_hist(gpx_path='./data/')
    heat.load_heatmap()
    heat.make_map(saturation_percentile=90)