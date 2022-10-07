import os
import time

import pandas as pd
import geopandas as gpd
from shapely import wkt

import spatialpandas
import spatialpandas.io

import cartopy.crs as ccrs

# import numpy as np

import holoviews as hv
import datashader as ds
from holoviews.operation.datashader import (
    datashade, inspect_polygons, inspect_points,
)

from bokeh.models import HoverTool

hv.extension('bokeh')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

hysets_geojson_loc = os.path.join(BASE_DIR, 'hysets_data/Hysets_stations.geojson')

hysets_gdf = gpd.read_file(hysets_geojson_loc)

geom_files = os.listdir(os.path.join(BASE_DIR, 'basin_data'))
processed_stns = list(set([e.split('_')[0] for e in geom_files]))

gdf = hysets_gdf[hysets_gdf['Official_ID'].isin(processed_stns)].copy()
gdf['processed'] = gdf['Official_ID'].apply(lambda l: l in processed_stns)
gdf.reset_index(inplace=True)

gdf = gdf[gdf.geom_type == 'Point'].to_crs(epsg=3857)
gdf = spatialpandas.GeoDataFrame(gdf)


# basin_polygon_data_loc = os.path.join(BASE_DIR, 'basin_data/')
# basin_geom_files = os.listdir(basin_polygon_data_loc)

# STATIONS = list(set([str(e.split('_')[0]) for e in basin_geom_files]))

# the content of these columns will be displayed via the hover tool
tooltips = [('Station ID', '@Official_ID'), 
('Name', '@Name')]

hover_tool = HoverTool(tooltips=tooltips)

# centroid = gdf.geometry.values.x.mean()

points = hv.Points(gdf, vdims=['Official_ID', 'Name', 'processed'],
label='Streamflow Monitoring Stations').opts(
    shared_axes=True,
    size=8, line_color='black', 
    tools=[hover_tool, 'tap'],
    nonselection_color='grey',
    nonselection_alpha=0.75)

# tiles = hv.element.tiles.StamenTerrainRetina().opts(width=600, height=550)
tiles = hv.element.tiles.StamenWatercolor().opts(xaxis=None, yaxis=None,min_height=700, responsive=True, shared_axes=True)

dx, dy = gdf[:1].geometry[0].x, gdf[:1].geometry[0].y
default_id = gdf[:1]['Official_ID'].values[0]

def get_geometry(station_id, geom_type):
    basin_path = os.path.join(BASE_DIR, f'basin_data/{station_id}_{geom_type}.geojson')
    if os.path.exists(basin_path):
        basin_polygon = gpd.read_file(basin_path)
        basin_polygon = basin_polygon.to_crs(3857)
        return basin_polygon
    else:
        return []

# Declare points as source of selection stream
selection = hv.streams.Selection1D(source=points)

def set_default_overlay():
    _og_poly = hv.Polygons([], label='HYSETS Polygon').opts(color='gold', alpha=0.5, show_legend=True)
    _derived_poly = hv.Polygons([], label='Validation Polygon').opts(color='dodgerblue', alpha=0.5, show_legend=True)

    _og_pt = hv.Points([], label='HYSETS Station Location').opts(marker='star', size=15, color='gold', line_color='black')
    _adj_pt = hv.Points([], label='Adjusted Pour Point').opts(marker='triangle', size=10, color='gold', line_color='black')

    _contours = hv.Path([], label='Contours').opts(color='chocolate', alpha=0.8)

    return hv.Overlay([_contours, _og_poly, _derived_poly, _og_pt, _adj_pt])


# Define function to compute histogram based on tap location
def station_selected(index):

    if len(index) == 0:
        return set_default_overlay()
    else:
        index = index[0]
    stn = points.iloc[index]
    stn_id = stn['Official_ID'][0]
    processed = stn['processed'][0]
    # print(index, stn_id)
    # if processed:
    basin = get_geometry(stn_id, 'derived') # get the basin polygon
    # basin = spatialpandas.GeoDataFrame(basin)
    basin_polygon = hv.Polygons(basin).opts(alpha=0.5, color='dodgerblue', show_legend=True)

    og_basin = get_geometry(stn_id, 'og_polygon')
    og_basin_polygon = hv.Polygons(og_basin, label='HYSETS Polygon').opts(alpha=0.5, color='gold', show_legend=True)

    og_stn_loc = get_geometry(stn_id, 'og_ppt')
    og_stn_loc_pt = hv.Points(og_stn_loc).opts(marker='star', size=15, color='gold', line_color='black')

    adjusted_stn_loc = get_geometry(stn_id, 'ppt_adjusted')
    adjusted_stn_loc_pt = hv.Points(adjusted_stn_loc).opts(marker='triangle', size=10, color='dodgerblue', line_color='black') 

    contours = get_geometry(stn_id, 'contours')
    if contours.empty:
        contours = []
    else:
        contours = contours.dissolve()
    contours = hv.Path(contours, label='Contours').opts(color='chocolate', alpha=0.8)
    geom_layout = [
        contours, 
        og_basin_polygon, basin_polygon,
        og_stn_loc_pt, adjusted_stn_loc_pt,
        ]
    all_geoms = gpd.GeoDataFrame(pd.concat([basin, og_basin, adjusted_stn_loc, og_stn_loc]))
    bounds = all_geoms.buffer(5E3).total_bounds
    min_x, max_x = bounds[0], bounds[2]

    return hv.Overlay(geom_layout).redim(x=hv.Dimension('x', range=(min_x, max_x)))

    
# Connect the Tap stream to the tap_histogram callback
selection_dmap = hv.DynamicMap(station_selected, streams=[selection])

layout = (tiles * points * selection_dmap).opts(title='HYSETS Basin Viewer', responsive=True, shared_axes=True)

renderer = hv.renderer('bokeh')
renderer = renderer.instance(mode='server')
renderer(layout)

