"""
Example script that takes a xlsx spreadsheet generated from microsoft forms, converts it to a set of metadata
inside a geojson file. Columns to skip can be added, (by default the Google email field is skipped). Then a template csv file
is created from the metadata, with rows being populated from id and project name. This is the updated with desired geometry,
points, polyline and polygons can be specified. See Readme.md for more information. Finally, the geometry csv and metadata geojson
are merged together into one geojson file that contains both the metadata and geometries. This can be imported into Tableau.
"""
from xls_2_geojson import xlsx_to_geojson_properties, xlsx_to_styling_template, merge_all

# define input file
input_file = "dummy_deployments.xlsx"
# convert metadata to geojson file (empty geometry)
xlsx_to_geojson_properties(input_file, "example_output/metadata.geojson")
# generate geometry template csv file (need to manually add features using excel and save as styling.csv)
xlsx_to_styling_template(input_file, "example_output/styling_template.csv")
# merge completed geometry and metadata geojson together
merge_all(metadata_geojson_path="example_output/metadata.geojson",
          kml_path="example_output/dummy.kml",
          styling_csv_path="example_output/styling.csv",
          output_path="example_output/out.geojson")

print("the end")