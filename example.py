"""
Example script that takes a xlsx spreadsheet generated from microsoft forms, converts it to a set of metadata
inside a geojson file. Columns to skip can be added, (by default the Google email field is skipped). Then a template csv file
is created from the metadata, with rows being populated from id and project name. This is the updated with desired geometry,
points, polyline and polygons can be specified. See Readme.md for more information. Finally, the geometry csv and metadata geojson
are merged together into one geojson file that contains both the metadata and geometries. This can be imported into Tableau.
"""
from xls_2_geojson import xlsx_to_geojson_properties, xlsx_to_geometry_template, merge_geometry_into_geojson

# define input file
input_file = "dummy_deployments.xlsx"
# convert metadata to geojson file (empty geometry)
xlsx_to_geojson_properties(input_file, "example_output/metadata.geojson")
# generate geometry template csv file (need to manually add features using excel)
xlsx_to_geometry_template(input_file, "example_output/geometry_template.csv")
# merge completed geometry and metadata geojson together
merge_geometry_into_geojson(geometry_csv="example_output/geometry.csv", metadata_geojson="example_output/metadata.geojson")

print("the end")