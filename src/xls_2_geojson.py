import json
import pandas as pd
from pathlib import Path
import ast
import re

"""
Convert an XLSX spreadsheet to GeoJSON-compatible metadata.

Each row becomes a GeoJSON Feature with a `properties` dict keyed by column headings.
Output is a FeatureCollection — geometry is set to null so points can be added later.
"""
def xlsx_to_geojson_properties(
    input_path: str,
    output_path: str = None,
    skip_columns: list = ["Google account email address"],
) -> dict:
    df = pd.read_excel(input_path)
    df.columns = [str(col).strip() for col in df.columns]

    skip = set(skip_columns or [])

    def strip_trailing_number(col: str):
        """Return (base_name, number) if col ends in a number, else (col, None)."""
        match = re.match(r"^(.*?)(\d+)$", col)
        if match:
            return match.group(1).rstrip(), int(match.group(2))
        return col, None

    # Pre-compute which column names share a base with at least one other column
    base_counts = {}
    for col in df.columns:
        if col in skip:
            continue
        base, num = strip_trailing_number(col)
        if num is not None:
            base_counts[base] = base_counts.get(base, 0) + 1

    # Only merge bases that appear more than once
    merge_bases = {base for base, count in base_counts.items() if count > 1}

    features = []
    for _, row in df.iterrows():
        properties = {}
        merged = {}  # base_name -> list of (number, value)

        for col in df.columns:
            if col in skip:
                continue

            val = row[col]
            if pd.isna(val):
                continue
            if hasattr(val, "item"):
                val = val.item()
            elif hasattr(val, "isoformat"):
                val = val.isoformat()

            base, num = strip_trailing_number(col)

            if num is not None and base in merge_bases:
                # Collect for merging, preserving order via the trailing number
                merged.setdefault(base, []).append((num, val))
            else:
                properties[col] = val

        # Flatten merged fields into sorted lists, dropping the numbers
        for base, pairs in merged.items():
            sorted_vals = [v for _, v in sorted(pairs)]
            properties[base] = sorted_vals

        features.append({
            "type": "Feature",
            "geometry": None,
            "properties": properties
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".geojson"))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    print(f"Converted {len(features)} rows -> {output_path}")
    return geojson

"""
Read an XLSX file, extract every ID field, and write a CSV template
with blank geometry columns ready to be filled in.
"""
def xlsx_to_geometry_template(
    input_path: str,
    output_path: str = None,
    id_column: str = "id",
    label_column: str = "Project Name",
) -> None:
    df = pd.read_excel(input_path)
    df.columns = [str(col).strip() for col in df.columns]

    # Case-insensitive match for the id column
    col_map = {col.lower(): col for col in df.columns}
    matched = col_map.get(id_column.lower())
    if matched is None:
        raise ValueError(
            f"Column '{id_column}' not found. Available columns: {list(df.columns)}"
        )
    ids = df[matched].dropna().tolist()
    # find labels
    matched = col_map.get(label_column.lower())
    if matched is None:
        print(f"Column '{label_column}' not found. will need to add manually")
        labels = ""
    else:
        labels = df[matched].dropna().tolist()
    # Normalise to plain Python types
    ids = [v.item() if hasattr(v, "item") else v for v in ids]
    labels = [v.item() if hasattr(v, "item") else v for v in labels]
    if output_path is None:
        output_path = str(Path(input_path).with_stem(Path(input_path).stem + "_geometry_template").with_suffix(".csv"))

    out_df = pd.DataFrame({"id": ids, "label":labels,"geotype": "", "colour": "", "coordinates": "[]"})
    out_df.to_csv(output_path, index=False)

    print(f"Written {len(ids)} rows → {output_path}")

"""
Read a geometry template CSV and a metadata GeoJSON, match by ID,
build the appropriate GeoJSON geometry, and write a combined output GeoJSON.
"""
def parse_coordinates(coord_str: str) -> list:
    """
    Parse a coordinate string into a list of [lon, lat] pairs.
    Accepts:
      "[lon,lat]"                        → single point
      "[[lon1,lat1],[lon2,lat2],...]"    → multiple points
    Always returns a list of [lon, lat] pairs.
    """
    parsed = ast.literal_eval(coord_str.strip())

    # Single point: [lon, lat] — wrap in a list
    if isinstance(parsed[0], (int, float)):
        return [parsed]

    return [list(p) for p in parsed]


def is_closed(coords: list) -> bool:
    """Return True if the first and last coordinate pairs are identical."""
    return coords[0] == coords[-1]


def build_geometry(geotype: str, coord_str: str) -> dict | None:
    """
    Build a GeoJSON geometry dict from a geotype string and coordinate string.
    Falls back gracefully if coordinates are missing or unparseable.
    """
    if not isinstance(coord_str, str) or not coord_str.strip():
        return None

    try:
        coords = parse_coordinates(coord_str)
    except Exception as e:
        print(f"  Warning: could not parse coordinates '{coord_str}': {e}")
        return None

    geotype = geotype.strip().lower() if isinstance(geotype, str) else ""

    if geotype == "point":
        return {
            "type": "Point",
            "coordinates": coords[0]
        }

    elif geotype == "polyline":
        return {
            "type": "LineString",
            "coordinates": coords
        }

    elif geotype == "polygon":
        # Ensure ring is closed
        ring = coords if is_closed(coords) else coords + [coords[0]]
        return {
            "type": "Polygon",
            "coordinates": [ring]   # GeoJSON polygons are arrays of rings
        }

    else:
        print(f"  Warning: unknown geotype '{geotype}', skipping geometry.")
        return None

"""
merge a geometry cvs and metadata geojson file together, matching entries using an id field
"""
def merge_geometry_into_geojson(
    geometry_csv: str,
    metadata_geojson: str,
    output_path: str = None,
    id_column: str = "id",
) -> dict:

    # Load inputs
    geometry_df = pd.read_csv(geometry_csv)
    geometry_df.columns = [col.strip() for col in geometry_df.columns]

    with open(metadata_geojson, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    # Build a lookup from id → LIST of geometry rows (one id may have many geometries)
    geometry_df[id_column] = geometry_df[id_column].astype(str)
    geometry_lookup = (
        geometry_df.groupby(id_column, sort=False)
        .apply(lambda g: g.to_dict(orient="records"))
        .to_dict()
    )

    matched = 0
    unmatched = 0
    new_features = []

    for feature in geojson["features"]:
        if id_column == "id" or id_column =="Id":
            id_column = "Id"
        else:
            raise NotImplementedError("only id columns called 'Id' are currently supported")
        feature_id = str(feature.get("properties", {}).get(id_column, ""))
        rows = geometry_lookup.get(feature_id)

        if not rows:
            # Keep the feature as-is (geometry stays None)
            new_features.append(feature)
            unmatched += 1
            continue

        for row in rows:
            geotype = row.get("geotype", "")
            coord_str = row.get("coordinates", "")
            geometry = build_geometry(geotype, coord_str)

            # Deep-copy properties so each sub-feature is independent
            props = dict(feature.get("properties") or {})

            colour = row.get("colour", "")
            if isinstance(colour, str) and colour.strip():
                props["colour"] = colour

            new_features.append({
                "type": "Feature",
                "geometry": geometry,
                "properties": props,
            })
            matched += 1

    geojson["features"] = new_features

    if output_path is None:
        stem = Path(metadata_geojson).stem
        output_path = str(Path(metadata_geojson).with_stem(stem + "_with_geometry"))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    print(f"Done: {matched} features created, {unmatched} unmatched → {output_path}")
    return geojson