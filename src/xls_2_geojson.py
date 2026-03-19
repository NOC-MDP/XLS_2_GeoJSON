import json
import pandas as pd
from pathlib import Path
import ast
import re
import xml.etree.ElementTree as ET

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
Read an XLSX file, extract every ID field, and write a CSV styling template
with blank colour and date columns ready to be filled in.
"""
def xlsx_to_styling_template(
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

    out_df = pd.DataFrame({"id": ids, "label":labels, "colour": "","date":""})
    out_df.to_csv(output_path, index=False)

    print(f"Written {len(ids)} rows → {output_path}")


# ---------------------------------------------------------------------------
# KML parsing
# ---------------------------------------------------------------------------

KML_NS = "http://www.opengis.net/kml/2.2"
KML_NS_ALT = "http://earth.google.com/kml/2.1"  # older Google Earth exports


def _ns(tag: str, ns: str) -> str:
    return f"{{{ns}}}{tag}"


def _parse_coord_string(coord_str: str) -> list:
    """
    Parse a KML coordinate string into a list of [lon, lat] pairs.
    KML format: 'lon,lat,alt lon,lat,alt ...' (alt is optional).
    """
    coords = []
    for token in coord_str.strip().split():
        parts = token.split(",")
        if len(parts) >= 2:
            coords.append([float(parts[0]), float(parts[1])])  # drop Z
    return coords


def _find(element, tag: str, ns: str):
    """Find a child element trying both KML namespace variants."""
    result = element.find(_ns(tag, ns))
    if result is None:
        result = element.find(_ns(tag, KML_NS_ALT))
    if result is None:
        result = element.find(tag)  # no namespace fallback
    return result


def _findall(element, tag: str, ns: str):
    results = element.findall(_ns(tag, ns))
    if not results:
        results = element.findall(_ns(tag, KML_NS_ALT))
    if not results:
        results = element.findall(tag)
    return results


def _parse_geometry(placemark, ns: str) -> dict | None:
    """Extract a GeoJSON-style geometry dict from a KML Placemark element."""

    # Point
    point = _find(placemark, "Point", ns)
    if point is not None:
        coords_el = _find(point, "coordinates", ns)
        if coords_el is not None:
            coords = _parse_coord_string(coords_el.text)
            if coords:
                return {"type": "Point", "coordinates": coords[0]}

    # LineString
    linestring = _find(placemark, "LineString", ns)
    if linestring is not None:
        coords_el = _find(linestring, "coordinates", ns)
        if coords_el is not None:
            return {"type": "LineString", "coordinates": _parse_coord_string(coords_el.text)}

    # Polygon
    polygon = _find(placemark, "Polygon", ns)
    if polygon is not None:
        rings = []
        outer = _find(polygon, "outerBoundaryIs", ns)
        if outer is not None:
            lr = _find(outer, "LinearRing", ns)
            if lr is not None:
                coords_el = _find(lr, "coordinates", ns)
                if coords_el is not None:
                    rings.append(_parse_coord_string(coords_el.text))
        for inner in _findall(polygon, "innerBoundaryIs", ns):
            lr = _find(inner, "LinearRing", ns)
            if lr is not None:
                coords_el = _find(lr, "coordinates", ns)
                if coords_el is not None:
                    rings.append(_parse_coord_string(coords_el.text))
        if rings:
            return {"type": "Polygon", "coordinates": rings}

    return None


def _iter_placemarks(element, ns: str):
    """Recursively yield all Placemark elements (handles nested Folders)."""
    for child in element:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "Placemark":
            yield child
        elif tag in ("Folder", "Document"):
            yield from _iter_placemarks(child, ns)


def parse_kml(path: str) -> dict:
    """
    Parse a KML file and return a dict of normalised name → GeoJSON geometry.
    """
    tree = ET.parse(path)
    root = tree.getroot()

    # Detect namespace from root tag
    ns = KML_NS
    if root.tag.startswith(f"{{{KML_NS_ALT}}}"):
        ns = KML_NS_ALT
    elif not root.tag.startswith("{"):
        ns = ""  # no namespace

    lookup = {}
    for placemark in _iter_placemarks(root, ns):
        name_el = _find(placemark, "name", ns)
        name = name_el.text.strip() if name_el is not None and name_el.text else None
        if not name:
            continue
        geometry = _parse_geometry(placemark, ns)
        if geometry:
            lookup[name.strip().lower()] = (name, geometry)

    return lookup  # { normalised_name: (original_name, geometry) }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalise(value) -> str:
    return str(value).strip().lower() if value is not None else ""


def load_geojson(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Main merge function
# ---------------------------------------------------------------------------

def merge_all(
        metadata_geojson_path: str,
        kml_path: str,
        styling_csv_path: str,
        output_path: str = None,
        metadata_name_field: str = "Project Name",
        styling_name_field: str = "label",
        styling_id_field: str = "id",
        styling_colour_field: str = "colour",
        styling_date_field: str = "date",
) -> dict:
    metadata = load_geojson(metadata_geojson_path)
    geometry_lookup = parse_kml(kml_path)

    styling_df = pd.read_csv(styling_csv_path)
    styling_df.columns = [col.strip() for col in styling_df.columns]

    styling_lookup = {}
    for _, row in styling_df.iterrows():
        name = normalise(row.get(styling_name_field, ""))
        if name:
            styling_lookup[name] = row

    geom_matched = 0
    geom_unmatched_names = []
    style_matched = 0
    style_unmatched_names = []

    for feature in metadata.get("features", []):
        props = feature.get("properties") or {}
        name = normalise(props.get(metadata_name_field))

        # --- Merge KML geometry ---
        geom_entry = geometry_lookup.get(name)
        if geom_entry:
            feature["geometry"] = geom_entry[1]
            geom_matched += 1
        else:
            geom_unmatched_names.append(props.get(metadata_name_field, "<no name>"))

        # --- Merge styling ---
        style_row = styling_lookup.get(name)
        if style_row is not None:
            colour = style_row.get(styling_colour_field)
            date = style_row.get(styling_date_field)
            style_id = style_row.get(styling_id_field)

            if pd.notna(colour) and str(colour).strip():
                props["colour"] = str(colour).strip()
            if pd.notna(date) and str(date).strip():
                props["date"] = str(date).strip()
            if pd.notna(style_id) and str(style_id).strip():
                props["style_id"] = str(style_id).strip()

            feature["properties"] = props
            style_matched += 1
        else:
            style_unmatched_names.append(props.get(metadata_name_field, "<no name>"))

    if output_path is None:
        stem = Path(metadata_geojson_path).stem
        output_path = str(Path(metadata_geojson_path).with_stem(stem + "_merged"))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"Geometry : {geom_matched} matched, {len(geom_unmatched_names)} unmatched")
    if geom_unmatched_names:
        print(f"  Unmatched metadata names : {geom_unmatched_names}")
        print(f"  Available KML names      : {[v[0] for v in geometry_lookup.values()]}")

    print(f"Styling  : {style_matched} matched, {len(style_unmatched_names)} unmatched")
    if style_unmatched_names:
        print(f"  Unmatched styling names  : {style_unmatched_names}")
        print(f"  Available styling names  : {list(styling_lookup.keys())}")

    print(f"Output   : {output_path}")

    return metadata