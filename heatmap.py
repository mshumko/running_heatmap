# This program makes a heatmap (plt.pcolormesh)
# of a bounded lat/lon area.

import glob
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

import gpxpy
import gpxpy.gpx

class Heatmap:
    def __init__(self):

        return
    
    def make_map(self):
        raise NotImplementedError

    def make_heatmap_hist(self):
        raise NotImplementedError

    
