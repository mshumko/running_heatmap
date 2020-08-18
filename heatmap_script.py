import argparse
import pprint

import heatmap

# Parse the user arguments.
parser = argparse.ArgumentParser(description='Outdoor excercise heatmap')
parser.add_argument('--no_hist', action='store_true', 
                help='Include this flag to not load and histogram the gpx files.')
parser.add_argument('--globe', action='store_true', 
                help='Use a global lat/lon grid (this is much slower to run).')
parser.add_argument('--gpx_path', default='./data/',
                help='The absolute path to the gpx files.')
parser.add_argument('--grid_res', type=float, default=0.0005,
                help='The grid resolution.')
parser.add_argument('--saturation_percentile', type=float, default=90,
                help=('The percentile of the histogram where greater '
                    'values are set to that percentile. This is a privacy '
                    'filter that avoids storing the true heatmap values in '
                    'the html file.'))
args = parser.parse_args()
print('Running the heatmap program with the following arguments:')
pprint.pprint(vars(args))

# Call the heatmap class.
heat = heatmap.Heatmap(global_grid=args.globe, grid_res=args.grid_res)
if not args.no_hist:
    heat.make_heatmap_hist(gpx_path=args.gpx_path)
heat.load_heatmap()
heat.make_map(saturation_percentile=args.saturation_percentile)