# XLS 2 GEOJSON (And Tableau!)

## Description

A lightweight Python pipeline for converting data held in an Excel spreadsheet into a fully-formed GeoJSON file, ready to be loaded into Tableau or any other GIS-aware tool.

The workflow is split into three functions:

| function                     | Purpose                                                                                                                                                                                                              |
|------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `xlsx_to_geojson_properties` | Reads an XLSX file and converts each row into a GeoJSON feature with a `properties` block. Geometry is left as `null` at this stage.                                                                                 |
| `xlsx_to_styling_template`   | Reads the same XLSX file, extracts every ID, and writes a styling CSV template with blank date and colour columns ready to be filled in.                                                                             |
| `merge_all`                  | Reads the completed styling template CSV and a kml file containing the geometry, matches each row to a feature in the metadata GeoJSON by ID, builds the correct geometry type, and writes a final combined GeoJSON. |

---

## Install

Python 3.12+ is recommended. Install the module as follows (a virtual env is recommended but not essential)

```bash
pip install .
```

The only dependencies are pandas and openpyxl which should be installed automatically if not already present.

---

## Usage

### Creating metadata GeoJSON file

Converts every row in your spreadsheet into a GeoJSON feature. Column headings become the keys inside each feature's `properties` block. Null values are omitted automatically.

```python
from xls_2_geojson import xlsx_to_geojson_properties

xlsx_to_geojson_properties(input_path="my_data.xlsx")
# Output: my_data.geojson

# Specify output path
xlsx_to_geojson_properties(input_path="my_data.xlsx", output_path="output/metadata.geojson")

# Skip columns you don't need
xlsx_to_geojson_properties(input_path="my_data.xlsx", skip_columns=["Start time"])

```

The output is a valid GeoJSON `FeatureCollection`. Each feature has `"geometry": null` at this point — geometry is added in a later step.

---

### Creating styling template CSV

Extracts every ID from your spreadsheet and writes a CSV template with blank columns for you to fill in:
The script will also populate the template with a label field to help with identifying the different entries by default
this is 'Project name' but this can be overridden if required. The populated columns are shown below:

```
id, label, colour, start date, end date
```

```python
from xls_2_geojson import xlsx_to_styling_template

xlsx_to_styling_template(input_path="my_data.xlsx")
# Output: my_data_styling_template.csv

# specify output path
xlsx_to_styling_template(input_path="my_data.xlsx", output_path="output/styling_template.csv")

# If your ID column has a different name
xlsx_to_styling_template(input_path="my_data.xlsx", id_column="Identification Number")

# If your label column has a different name
xlsx_to_styling_template(input_path="my_data.xlsx", label_column="Company")
```

Open the output CSV in Excel or any text editor and fill in the colour and date columns for each row. 
See the [Adding geometry](#adding-geometry) section below for the expected format.

---

### Adding geometry

The merge_all function expects an kml file containing the desired geometry, this can be created in google earth pro. Storing 
all layers in a folder and then exporting it as a kml should be compatible. Points, polylines and polygons are all supported

### Adding styling
The styling template allows a colour to be set (this is a string that is associated within tableau to a specific colour) and a 
date. The date string needs to be compatible with tableau, such as standard excel dates. e.g. 01/01/2027

**`colour`** — a category label used for styling in Tableau (e.g. `red`, `blue`, `green`). Leave blank if not needed.

**`start date`** — used for filtering data in Tableau (e.g. `01/01/2027`). Leave blank if not needed

**`end date`** — used for filtering data in Tableau (e.g. `01/01/2028`). Leave blank if not needed

---

### Merging geometry with metadata

Once the styling template CSV is filled in, and the kml file is created run the merge script to combine it with the metadata GeoJSON:

```python
from xls_2_geojson import merge_all

merge_all(metadata_geojson_path="metadata.geojson", kml_path="geometry.kml", styling_csv_path="styling.csv")
# Output: metadata_merged.geojson

# Specify output path
merge_all(metadata_geojson_path="metadata.geojson", kml_path="geometry.kml", styling_csv_path="styling.csv", output_path="merged.geojson")

# If your ID column has a different name
merge_all(metadata_geojson_path="metadata.geojson", kml_path="geometry.kml", styling_csv_path="styling.csv",styling_id_field="ID")
```

The script will print a summary of how many features were matched and updated. Any features without a matching ID in the template will retain `"geometry": null`.

---

### Adding to Tableau

1. Open Tableau Desktop and create a new workbook.
2. Under **Connect**, choose **Spatial file** and select your output `.geojson` file.
3. Tableau will automatically recognise the geometry and create a spatial data source.
4. Drag the **Geometry** field onto the canvas — Tableau will render points, lines, or polygons depending on the geometry type of each feature.
5. All fields from `properties` will appear as dimensions and measures in the data pane, ready to use.

---

### Configuration and styling within Tableau

**Colour by category**

If you populated the `colour` field in your template with category labels (e.g. `red`, `blue`, `green`):

1. Drag the **colour** field onto the **Color** shelf.
2. Click **Color → Edit Colors** to assign a specific color to each category value manually.

**Tooltips**

All `properties` fields are available as tooltip fields. Go to **Tooltip** on the Marks card to customise which fields appear and how they are labelled.

**Filtering**

Any property field can be dragged onto the **Filters** shelf to allow interactive filtering of features on the map.

---

## Example Script

A minimal end-to-end example pulling all three steps together:

```python
from xls_2_geojson import xlsx_to_geojson_properties, xlsx_to_styling_template
from xls_2_geojson import xlsx_to_geometry_template
from xls_2_geojson import merge_geometry_into_geojson

INPUT_XLSX = "my_data.xlsx"
METADATA_GEOJSON = "my_data.geojson"
STYLING_CSV = "my_data_styling_template.csv"
KML_FILE = "my_spatial.kml"
OUTPUT_GEOJSON = "my_data_final.geojson"

# Step 1: Convert spreadsheet rows to GeoJSON metadata
xlsx_to_geojson_properties(
    INPUT_XLSX,
    METADATA_GEOJSON,
)

# Step 2: Generate a geometry template CSV from the same spreadsheet
# NOTE only id columns called 'Id' in spreadsheet are cuurently supported
xlsx_to_styling_template(
    INPUT_XLSX,
    STYLING_CSV,

)

# --- Fill in the template CSV manually at this point ---
# --- Create KML file in google earth pro with layer names matching project names ---

# Step 3: Merge the completed template and KML back into the GeoJSON
merge_all(
    METADATA_GEOJSON,
    KML_FILE,
    STYLING_CSV,
    OUTPUT_GEOJSON,
)
```
There is also an example python script in the repository that uses dummy input data (and a prefilled out styling 
and kml file) to demostrate how the module is expected to be used.

```shell
$ python example.py
```

---
