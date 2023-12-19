#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Simon R Proud
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""An example script showing how to detect fires using pyfires and Himawari/AHI data."""

# By default Dask will use all available CPU cores. On powerful machines this can
# actually slow down processing, so here we limit the cores it can use.
# For more info, see: https://satpy.readthedocs.io/en/stable/faq.html#why-is-satpy-slow-on-my-powerful-machine
import dask
dask.config.set(num_workers=8)

# Set some satpy configuration options for data caching.
# We cache the lats / lons as they should not change when processing a time series.
# But we do not cache the sensor angles, and for Himawari these do change!
# For processing other satellites you may want to cache the angles.
import satpy
satpy.config.set({'cache_dir': "D:/sat_data/cache/"})
satpy.config.set({'cache_sensor_angles': False})
satpy.config.set({'cache_lonlats': True})

# Final imports
from pyfires.PYF_basic import initial_load, save_output
from pyfires.PYF_detection import run_dets, stage1_tests
from satpy import Scene
from tqdm import tqdm
from glob import glob
import os

from dask.diagnostics import Profiler, ResourceProfiler, visualize
from datetime import datetime

# Satpy sometimes spits out some warnings for divide by zero.
# These are harmless so let's ignore them.
import warnings
warnings.filterwarnings('ignore')

def main():
    # Set the top-level input directory (containing ./HHMM/ subdirs following NOAA AWS format)
    input_file_dir = 'D:/sat_data/ahi_main/in/'
    # Set the output directory where FRP images will be saved.
    output_img_dir = 'D:/sat_data/ahi_main/out/'

    # Set an X-Y bounding box for cropping the input data.
    bbox = None#(-1600000, -2770000, 690000, -1040000)

    # Search for input timeslots.
    idirs = glob(f'{input_file_dir}/*1110*')
    idirs.sort()

    # Set up a dictionary mapping band type names to the AHI channel names.
    # 'vi1_band' is the ~0.64 micron visible channel.
    # 'mir_band' is the ~3.9 micron mid-infrared channel.
    # 'lwi_band' is the ~10.4 micron long-wave infrared channel.
    bdict = {'vi1_band': 'B03',
             'mir_band': 'B07',
             'lwi_band': 'B13'}

    # Loop over timeslots and process data...
    for cdir in tqdm(idirs):
        if cdir == idirs[0]:
            print("\n")

        st = datetime.utcnow()
        # Find files and ensure we have enough to process.
        ifiles_l15 = glob(cdir+'/*.DAT')
        if len(ifiles_l15) < 40:
            continue

        # Create a simple Scene to simplift saving the results.
        scn = Scene(reader='ahi_hsd', filenames=ifiles_l15)
        scn.load(['B07'])
        if bbox:
            scn = scn.crop(xy_bbox=bbox)

        # Get timeslot from filename
        curf = ifiles_l15[0]
        pos = curf.find('HS_H')
        dtstr = curf[pos+7:pos+7+13]

        # Set output filename
        outf1 = f'{output_img_dir}/pfp_{dtstr}00.tif'
        outf2 = f'{output_img_dir}/t1_{dtstr}00.tif'
        outf3 = f'{output_img_dir}/t2_{dtstr}00.tif'

        # Skip files we've already processed
        #if not os.path.isfile(outf1) and not os.path.isfile(outf2):
        if True:
            # Load the initial data.
            # Here we don't load the land/sea mask as we're cropping and this is
            # not (yet) supported by pyfires. For full disk processing you will
            # likely get more accurate results by enabling the land/sea mask.
            data_dict = initial_load(ifiles_l15,        # Input file list
                                     'ahi_hsd',         # Satpy reader name
                                     bdict,             # Band mapping dict
                                     do_load_lsm=True, # Don't load land-sea mask
                                     bbox=bbox)         # Bounding box for cropping

            data_dict['PFP'] = stage1_tests(data_dict['MIR__BT'],
                                            data_dict['BTD'],
                                            data_dict['VI1_DIFF'],
                                            data_dict['SZA'],
                                            data_dict['LSM'],
                                            ksizes=[5, 7, 9],
                                            do_lsm_mask=True)

            # Run the detection algorithm. This returns a boolean mask of the
            # fire detections as well as the actual fire radiative power data.
            #fire_dets, frp_data = run_dets(data_dict)
           # save_output(scn, fire_dets, 'fire_dets', outf1, ref='B07')
            #save_output(scn, frp_data, 'fire_dets', outf2, ref='B07')
            save_output(scn, data_dict['PFP'], 'BTD', outf1, ref='B07')
            #save_output(scn, dd['t1'], 'VI1_DIFF', outf2, ref='B07')
            #save_output(scn, dd['t2'], 'MIR__BT', outf3, ref='B07')

        en = datetime.utcnow()

        print((en-st).total_seconds())
        #break


if __name__ == "__main__":
    with Profiler() as prof, ResourceProfiler(dt=0.25) as rprof:
        main()
    visualize([prof, rprof], show=False, save=True, filename="D:/sat_data/ahi_main/frp_vis.html")
