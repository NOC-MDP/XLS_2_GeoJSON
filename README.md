# XLS 2 GEOJSON (And Tableau!)

## Description

A lightweight Python pipeline for converting data held in an Excel spreadsheet into a fully-formed GeoJSON file, ready to be loaded into Tableau or any other GIS-aware tool.

The workflow is split into three focused scripts:

| Script | Purpose |
|---|---|
| `xlsx_to_geojson_properties.py` | Reads an XLSX file and converts each row into a GeoJSON feature with a `properties` block. Geometry is left as `null` at this stage. |
| `xlsx_to_geometry_template.py` | Reads the same XLSX file, extracts every ID, and writes a CSV template with blank geometry columns ready to be filled in. |
| `merge_geometry_into_geojson.py` | Reads the completed geometry template CSV, matches each row to a feature in the metadata GeoJSON by ID, builds the correct geometry type, and writes a final combined GeoJSON. |

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

### Creating geometry template CSV

Extracts every ID from your spreadsheet and writes a CSV template with blank columns for you to fill in:
The script will also populate the template with a label field to help with identifying the different entries by default
this is 'Project name' but this can be overridden if required.

```
id, geotype, colour, coordinates
```

```python
from xls_2_geojson import xlsx_to_geometry_template

xlsx_to_geometry_template(input_path="my_data.xlsx")
# Output: my_data_geometry_template.csv

# specify output path
xlsx_to_geometry_template(input_path="my_data.xlsx", output_path="output/geometry_template.csv")

# If your ID column has a different name
xlsx_to_geometry_template(input_path="my_data.xlsx", id_column="Identification Number")

# If your label column has a different name
xlsx_to_geometry_template(input_path="my_data.xlsx", label_column="Company")
```

Open the output CSV in Excel or any text editor and fill in the geometry columns for each row. See the [Adding geometry](#adding-geometry) section below for the expected format.

---

### Adding geometry

Fill in the geometry template CSV with the following values:

**`geotype`** — one of:

| Value | Geometry |
|---|---|
| `point` | A single location |
| `polyline` | An ordered sequence of connected points |
| `polygon` | A closed shape |

**`coordinates`** — coordinates as a JSON-style string:

| geotype | Format | Example |
|---|---|---|
| `point` | `[lon,lat]` | `[-1.5,53.8]` |
| `polyline` | `[[lon1,lat1],[lon2,lat2],...]` | `[[-1.5,53.8],[-1.6,53.9]]` |
| `polygon` | `[[lon1,lat1],...,[lon1,lat1]]` | `[[-1.5,53.8],[-1.6,53.9],[-1.4,54.0],[-1.5,53.8]]` |

> Note: polygons are automatically closed during processing if the first and last points do not match, so you don't need to repeat the first point manually.

**`colour`** — a category label used for styling in Tableau (e.g. `red`, `blue`, `green`). Leave blank if not needed.

---

### Merging geometry with metadata

Once the geometry template CSV is filled in, run the merge script to combine it with the metadata GeoJSON:

```python
from xls_2_geojson import merge_geometry_into_geojson

merge_geometry_into_geojson(geometry_csv="geometry.csv", metadata_geojson="metadata.geojson")
# Output: metadata_with_geometry.geojson

# Specify output path
merge_geometry_into_geojson(geometry_csv="geometry.csv", metadata_geojson="metadata.geojson", output_path="output/final.geojson")

# If your ID column has a different name
merge_geometry_into_geojson(geometry_csv="geometry.csv", metadata_geojson="metadata.geojson", id_column="Identification Number")
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

**Colour by measure**

To colour features by a numeric property (e.g. a score or count):

1. Drag the numeric field onto the **Color** shelf.
2. Tableau will apply a continuous color gradient automatically. Use **Edit Colors** to change the palette or set custom min/max values.

**Tooltips**

All `properties` fields are available as tooltip fields. Go to **Tooltip** on the Marks card to customise which fields appear and how they are labelled.

**Filtering**

Any property field can be dragged onto the **Filters** shelf to allow interactive filtering of features on the map.

---

## Example Script

A minimal end-to-end example pulling all three steps together:

```python
from xls_2_geojson import xlsx_to_geojson_properties
from xls_2_geojson import xlsx_to_geometry_template
from xls_2_geojson import merge_geometry_into_geojson

INPUT_XLSX       = "my_data.xlsx"
METADATA_GEOJSON = "my_data.geojson"
TEMPLATE_CSV     = "my_data_geometry_template.csv"
OUTPUT_GEOJSON   = "my_data_final.geojson"

# Step 1: Convert spreadsheet rows to GeoJSON metadata
xlsx_to_geojson_properties(
    INPUT_XLSX,
    METADATA_GEOJSON,
    skip_columns=["Email", "Start time"]
)

# Step 2: Generate a geometry template CSV from the same spreadsheet
# NOTE only id columns called 'Id' in spreadsheet are cuurently supported
xlsx_to_geometry_template(
    INPUT_XLSX,
    TEMPLATE_CSV,

)

# --- Fill in the template CSV manually at this point ---

# Step 3: Merge the completed template back into the GeoJSON
# NOTE only id columns called 'Id' in spreadsheet are cuurently supported
merge_geometry_into_geojson(
    TEMPLATE_CSV,
    METADATA_GEOJSON,
    OUTPUT_GEOJSON,
)
```
---
## Issues

id column is only supported as 'Id' which is the default field in Microsoft forms. This is due a mismatch in the code where 
it needs to be 'id' at some points and 'Id' at others. So currently the default 'id' string should be used and not overridden