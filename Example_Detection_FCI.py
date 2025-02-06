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

"""An example script showing how to detect fires using pyfires and MTG/FCI data."""

# By default Dask will use all available CPU cores. On powerful machines this can
# actually slow down processing, so here we limit the cores it can use.
# For more info, see: https://satpy.readthedocs.io/en/stable/faq.html#why-is-satpy-slow-on-my-powerful-machine
from tempfile import gettempdir
from pathlib import Path
import dask
dask.config.set(num_workers=2)

# Set some satpy configuration options for data caching.
# We cache the lats / lons as they should not change when processing a time series.
# But we do not cache the sensor angles, and for Himawari these do change!
# For processing other satellites you may want to cache the angles.
import satpy
satpy.config.set({'cache_dir': str(Path(f"{gettempdir()}").joinpath('cache'))})
satpy.config.set({'cache_sensor_angles': False})
satpy.config.set({'cache_lonlats': True})

# Final imports
from pyfires.PYF_basic import initial_load, save_output_csv, set_default_values, sort_l1
from pyfires.PYF_detection import run_dets
from satpy import Scene, find_files_and_readers, DataQuery


from datetime import datetime, timezone

# Satpy sometimes spits out some warnings for divide by zero.
# These are harmless so let's ignore them.
import warnings
warnings.filterwarnings('ignore')


def alternative_load(
    infiles_l1,
    l1_reader,
    bdict,
    do_load_lsm=True,
    bbox=None,
) -> dict:
    # Construct queries
    vi1_rad = DataQuery(name=bdict['vi1_band'], calibration="radiance")
    vi2_rad = DataQuery(name=bdict['vi2_band'], calibration="radiance")
    mir_rad = DataQuery(name=bdict['mir_band'], calibration="radiance")
    mir_bt = DataQuery(name=bdict['mir_band'], calibration="brightness_temperature")
    lwi_rad = DataQuery(name=bdict['lwi_band'], calibration="radiance")
    lwi_bt = DataQuery(name=bdict['lwi_band'], calibration="brightness_temperature")

    blist = [vi1_rad, vi2_rad, mir_rad, lwi_rad, mir_bt, lwi_bt]

    scn = Scene(infiles_l1, reader=l1_reader)
    scn.load(blist, calibration='radiance', generate=False)

    if bbox:
        scn = scn.crop(xy_bbox=bbox)

    scnr = scn.resample(scn.coarsest_area(), resampler='native')
    return sort_l1(
        scnr[vi1_rad],
        scnr[vi2_rad],
        scnr[mir_rad],
        scnr[lwi_rad],
        scnr[mir_bt],
        scnr[lwi_bt],
        bdict,
        do_load_lsm=do_load_lsm,
    )


def main():
    with dask.config.set({"array.chunk-size": "10MiB"}):
        # Set the top-level input directory (containing ./HHMM/ subdirs following NOAA AWS format)
        input_file_dir = Path("testfiles").joinpath("in/hr")
        # Set the output directory where FRP images will be saved.
        output_img_dir = Path("testfiles").joinpath("out/hr")

        # Set an X-Y bounding box for cropping the input data.
        bbox = None

        # Set up a dictionary mapping band type names to the AHI channel names. TODO change for FCI
        # 'vi1_band' is the ~0.64 micron visible channel.
        # 'mir_band' is the ~3.9 micron mid-infrared channel.
        # 'lwi_band' is the ~10.4 micron long-wave infrared channel.
        bdict = {'vi1_band': 'vis_06',
                 'vi2_band': 'nir_22',
                 'mir_band': 'ir_38',
                 'lwi_band': 'ir_105'}
        
        st = datetime.now(timezone.utc)

        files = find_files_and_readers(base_dir=input_file_dir, reader="fci_l1c_nc")

        if len(files["fci_l1c_nc"]) < 40:
            print("Not enough files")
            return

        # Load the initial data.
        fci_files = [str(f) for f in input_file_dir.glob("*.nc")]

        # Here we don't load the land/sea mask as we're cropping and this is
        # not (yet) supported by pyfires. For full disk processing you will
        # likely get more accurate results by enabling the land/sea mask.
        initial_load_data_dict = initial_load(
            fci_files,          # Input file list
            'fci_l1c_nc',       # Satpy reader name
            bdict,              # Band mapping dict
            do_load_lsm=False,  # Don't load land-sea mask
            bbox=bbox           # Bounding box for cropping
        )

        alternative_load_data_dict = alternative_load(
            fci_files,          # Input file list
            'fci_l1c_nc',       # Satpy reader name
            bdict,              # Band mapping dict
            do_load_lsm=False,  # Don't load land-sea mask
            bbox=bbox           # Bounding box for cropping
        )

        
        # direct load
        vi1_rad = DataQuery(name=bdict['vi1_band'], calibration="radiance")
        vi2_rad = DataQuery(name=bdict['vi2_band'], calibration="radiance")
        mir_rad = DataQuery(name=bdict['mir_band'], calibration="radiance")
        mir_bt = DataQuery(name=bdict['mir_band'], calibration="brightness_temperature")
        lwi_rad = DataQuery(name=bdict['lwi_band'], calibration="radiance")
        lwi_bt = DataQuery(name=bdict['lwi_band'], calibration="brightness_temperature")

        blist = [vi1_rad, vi2_rad, mir_rad, lwi_rad, mir_bt, lwi_bt]

        scn = Scene(fci_files, reader='fci_l1c_nc')
        scn.load(blist, calibration='radiance', generate=False)

        if bbox:
            scn = scn.crop(xy_bbox=bbox)

        scnr = scn.resample(scn.coarsest_area(), resampler='native')
        
        # Here we don't load the land/sea mask as we're cropping and this is
        # not (yet) supported by pyfires. For full disk processing you will
        # likely get more accurate results by enabling the land/sea mask.
        direct_load_data_dict = sort_l1(
            scnr[vi1_rad],
            scnr[vi2_rad],
            scnr[mir_rad],
            scnr[lwi_rad],
            scnr[mir_bt],
            scnr[lwi_bt],
            bdict,
            do_load_lsm=False,
        )

        # # Set up the constants used during processing
        data_dict = set_default_values(direct_load_data_dict)

        # Run the detection algorithm. This returns a boolean mask of the
        # fire detections as well as the actual fire radiative power data.
        data_dict = run_dets(data_dict)
        # save_output(scn, data_dict['frp_est'], 'frp_est', outf, ref='B07')
        save_output_csv(data_dict, str(output_img_dir.joinpath("fires.csv")))

    en = datetime.now(timezone.utc)

    print((en-st).total_seconds())

if __name__ == "__main__":
    #with Profiler() as prof, ResourceProfiler(dt=0.25) as rprof:
    main()
    #    visualize([prof, rprof], show=False, save=True, filename="/home/ubuntu/data/frp_vis.html")
