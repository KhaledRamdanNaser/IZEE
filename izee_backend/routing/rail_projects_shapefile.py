import math
import struct
from pathlib import Path


LRT_SHAPE_SEGMENTS = {
    "LRT_ADLY_10RAMADAN_0": [
        ("ET2", "LRT_ADLY_MANSOUR", "LRT_BADR"),
        ("ET1", "LRT_BADR", "LRT_NEW_OBOUR"),
        ("ET1", "LRT_NEW_OBOUR", "LRT_CITY_CENTER"),
    ],
    "LRT_ADLY_10RAMADAN_1": [
        ("ET1", "LRT_CITY_CENTER", "LRT_NEW_OBOUR"),
        ("ET1", "LRT_NEW_OBOUR", "LRT_BADR"),
        ("ET2", "LRT_BADR", "LRT_ADLY_MANSOUR"),
    ],
    "LRT_ADLY_CAPITAL_0": [
        ("ET2", "LRT_ADLY_MANSOUR", "LRT_ARTS_CULTURE"),
        ("ET2", "LRT_ARTS_CULTURE", "LRT_CENTRAL_CAPITAL"),
    ],
    "LRT_ADLY_CAPITAL_1": [
        ("ET2", "LRT_CENTRAL_CAPITAL", "LRT_ARTS_CULTURE"),
        ("ET2", "LRT_ARTS_CULTURE", "LRT_ADLY_MANSOUR"),
    ],
}


MONORAIL_SHAPE_SEGMENTS = {
    "MONORAIL_EAST_NILE_0": [
        ("MR2", "MONORAIL_STADIUM", "MONORAIL_JUSTICE_CITY"),
    ],
    "MONORAIL_EAST_NILE_1": [
        ("MR2", "MONORAIL_JUSTICE_CITY", "MONORAIL_STADIUM"),
    ],
}



def haversine_meters(lat1, lon1, lat2, lon2):
    radius_meters = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return radius_meters * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def cumulative_distances(points):
    distances = [0.0]

    for previous, current in zip(points, points[1:]):
        distances.append(
            distances[-1]
            + haversine_meters(
                previous["lat"],
                previous["lon"],
                current["lat"],
                current["lon"],
            )
        )

    return distances


def read_projection(shapefile_path):
    prj_path = Path(shapefile_path).with_suffix(".prj")

    if not prj_path.exists():
        return None

    return prj_path.read_text(encoding="utf-8", errors="replace").strip()


def read_dbf_records(dbf_path):
    records = []

    with Path(dbf_path).open("rb") as handle:
        header = handle.read(32)
        record_count = struct.unpack("<I", header[4:8])[0]
        record_length = struct.unpack("<H", header[10:12])[0]
        fields = []

        while True:
            field_descriptor = handle.read(32)

            if field_descriptor[0] == 0x0D:
                break

            field_name = (
                field_descriptor[:11]
                .split(b"\x00", 1)[0]
                .decode("ascii", errors="replace")
            )
            field_type = chr(field_descriptor[11])
            field_length = field_descriptor[16]
            decimal_count = field_descriptor[17]
            fields.append({
                "name": field_name,
                "type": field_type,
                "length": field_length,
                "decimal_count": decimal_count,
            })

        for _ in range(record_count):
            raw_record = handle.read(record_length)

            if not raw_record or raw_record[:1] == b"*":
                continue

            position = 1
            record = {}

            for field in fields:
                raw_value = raw_record[position:position + field["length"]]
                position += field["length"]
                record[field["name"]] = raw_value.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

            records.append(record)

    return fields, records


def read_shp_polylines(shp_path):
    polylines = []

    with Path(shp_path).open("rb") as handle:
        header = handle.read(100)
        shape_type = struct.unpack("<i", header[32:36])[0]
        bbox = struct.unpack("<4d", header[36:68])

        while True:
            record_header = handle.read(8)

            if not record_header:
                break

            record_number, record_length_words = struct.unpack(">2i", record_header)
            content = handle.read(record_length_words * 2)

            if len(content) < 44:
                continue

            record_shape_type = struct.unpack("<i", content[:4])[0]

            if record_shape_type != 3:
                continue

            record_bbox = struct.unpack("<4d", content[4:36])
            part_count, point_count = struct.unpack("<2i", content[36:44])
            parts_offset = 44
            points_offset = parts_offset + 4 * part_count
            points = []

            for point_index in range(point_count):
                offset = points_offset + point_index * 16
                lon, lat = struct.unpack("<2d", content[offset:offset + 16])
                points.append({"lat": lat, "lon": lon})

            polylines.append({
                "record_number": record_number,
                "shape_type": record_shape_type,
                "bbox": record_bbox,
                "part_count": part_count,
                "point_count": point_count,
                "points": points,
            })

    return {
        "shape_type": shape_type,
        "bbox": bbox,
        "records": polylines,
    }


def load_rail_project_records(shapefile_path):
    shapefile_path = Path(shapefile_path)
    dbf_path = shapefile_path.with_suffix(".dbf")

    if not shapefile_path.exists() or not dbf_path.exists():
        return None

    fields, dbf_records = read_dbf_records(dbf_path)
    shp_data = read_shp_polylines(shapefile_path)
    records = []

    for attributes, geometry in zip(dbf_records, shp_data["records"]):
        records.append({
            "attributes": attributes,
            "geometry": geometry,
        })

    return {
        "projection": read_projection(shapefile_path),
        "shape_type": shp_data["shape_type"],
        "bbox": shp_data["bbox"],
        "fields": fields,
        "records": records,
    }


def nearest_point_index(points, stop):
    stop_lat = float(stop["stop_lat"])
    stop_lon = float(stop["stop_lon"])
    best_index = None
    best_distance = float("inf")

    for index, point in enumerate(points):
        distance = haversine_meters(
            stop_lat,
            stop_lon,
            point["lat"],
            point["lon"],
        )

        if distance < best_distance:
            best_index = index
            best_distance = distance

    return best_index, best_distance


def extract_segment_points(records, route_id, start_stop, end_stop, max_endpoint_distance_m=600):
    candidates = []

    for record in records:
        attributes = record["attributes"]

        if attributes.get("route_id") != route_id:
            continue

        points = record["geometry"]["points"]
        start_index, start_distance = nearest_point_index(points, start_stop)
        end_index, end_distance = nearest_point_index(points, end_stop)

        if start_index is None or end_index is None:
            continue

        if start_index >= end_index:
            continue

        if start_distance > max_endpoint_distance_m or end_distance > max_endpoint_distance_m:
            continue

        candidates.append({
            "record": record,
            "start_index": start_index,
            "end_index": end_index,
            "start_distance_m": start_distance,
            "end_distance_m": end_distance,
            "score": start_distance + end_distance,
        })

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: candidate["score"])
    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None

    if second and abs(second["score"] - best["score"]) < 1:
        return None

    points = best["record"]["geometry"]["points"][
        best["start_index"]:best["end_index"] + 1
    ]

    return {
        "points": points,
        "record_number": best["record"]["geometry"]["record_number"],
        "source_route_id": route_id,
        "source_route_long": best["record"]["attributes"].get("route_long", ""),
        "source_status": best["record"]["attributes"].get("status", ""),
        "start_distance_m": round(best["start_distance_m"], 2),
        "end_distance_m": round(best["end_distance_m"], 2),
    }


def build_shape_rows_from_rail_projects(shapefile_path, stops_by_id):
    dataset = load_rail_project_records(shapefile_path)

    if dataset is None:
        return None, {
            "used": False,
            "reason": "shapefile_or_dbf_missing",
        }

    lrt_records = [
        record for record in dataset["records"]
        if record["attributes"].get("status") == "ET(LRT)"
    ]
    report = {
        "used": False,
        "source": str(shapefile_path),
        "projection": dataset["projection"],
        "shape_type": dataset["shape_type"],
        "bbox": dataset["bbox"],
        "dbf_columns": dataset["fields"],
        "lrt_record_count": len(lrt_records),
        "lrt_records": [
            {
                "record_number": record["geometry"]["record_number"],
                "route_id": record["attributes"].get("route_id"),
                "route_short_name": record["attributes"].get("route_shor"),
                "route_long_name": (
                    record["attributes"].get("route_long", "")
                    + record["attributes"].get("route_desc", "")
                ).strip(),
                "status": record["attributes"].get("status"),
                "point_count": record["geometry"]["point_count"],
                "part_count": record["geometry"]["part_count"],
            }
            for record in lrt_records
        ],
        "shape_mappings": [],
        "skipped": [],
    }

    shape_rows = []

    for shape_id, segments in LRT_SHAPE_SEGMENTS.items():
        stitched_points = []
        segment_reports = []

        for source_route_id, start_stop_id, end_stop_id in segments:
            segment = extract_segment_points(
                dataset["records"],
                source_route_id,
                stops_by_id[start_stop_id],
                stops_by_id[end_stop_id],
            )

            if segment is None:
                report["skipped"].append({
                    "shape_id": shape_id,
                    "source_route_id": source_route_id,
                    "from_stop_id": start_stop_id,
                    "to_stop_id": end_stop_id,
                    "reason": "missing_or_ambiguous_segment",
                })
                return None, report

            segment_points = segment["points"]

            if stitched_points and segment_points:
                previous = stitched_points[-1]
                current = segment_points[0]
                if haversine_meters(
                    previous["lat"],
                    previous["lon"],
                    current["lat"],
                    current["lon"],
                ) < 5:
                    segment_points = segment_points[1:]

            stitched_points.extend(segment_points)
            segment_reports.append({
                key: value
                for key, value in segment.items()
                if key != "points"
            })

        distances = cumulative_distances(stitched_points)
        report["shape_mappings"].append({
            "shape_id": shape_id,
            "segments": segment_reports,
            "point_count": len(stitched_points),
            "distance_km": round(distances[-1] / 1000, 3) if distances else 0,
        })

        for index, point in enumerate(stitched_points):
            shape_rows.append({
                "shape_id": shape_id,
                "shape_pt_lat": round(point["lat"], 7),
                "shape_pt_lon": round(point["lon"], 7),
                "shape_pt_sequence": index + 1,
                "shape_dist_traveled": round(distances[index] / 1000, 3),
            })

    report["used"] = True
    report["generated_shape_points"] = len(shape_rows)
    return shape_rows, report


def build_monorail_shape_rows_from_rail_projects(shapefile_path, stops_by_id):
    dataset = load_rail_project_records(shapefile_path)

    if dataset is None:
        return None, {
            "used": False,
            "reason": "shapefile_or_dbf_missing",
        }

    monorail_records = [
        record for record in dataset["records"]
        if record["attributes"].get("status") == "Monorail"
    ]
    report = {
        "used": False,
        "source": str(shapefile_path),
        "projection": dataset["projection"],
        "shape_type": dataset["shape_type"],
        "bbox": dataset["bbox"],
        "dbf_columns": dataset["fields"],
        "monorail_record_count": len(monorail_records),
        "monorail_records": [
            {
                "record_number": record["geometry"]["record_number"],
                "route_id": record["attributes"].get("route_id"),
                "route_short_name": record["attributes"].get("route_shor"),
                "route_long_name": (
                    record["attributes"].get("route_long", "")
                    + record["attributes"].get("route_desc", "")
                ).strip(),
                "status": record["attributes"].get("status"),
                "point_count": record["geometry"]["point_count"],
                "part_count": record["geometry"]["part_count"],
            }
            for record in monorail_records
        ],
        "shape_mappings": [],
        "skipped": [],
    }

    shape_rows = []

    for shape_id, segments in MONORAIL_SHAPE_SEGMENTS.items():
        stitched_points = []
        segment_reports = []

        for source_route_id, start_stop_id, end_stop_id in segments:
            segment = extract_segment_points(
                dataset["records"],
                source_route_id,
                stops_by_id[start_stop_id],
                stops_by_id[end_stop_id],
            )

            if segment is None:
                report["skipped"].append({
                    "shape_id": shape_id,
                    "source_route_id": source_route_id,
                    "from_stop_id": start_stop_id,
                    "to_stop_id": end_stop_id,
                    "reason": "missing_or_ambiguous_segment",
                })
                return None, report

            segment_points = segment["points"]

            if stitched_points and segment_points:
                previous = stitched_points[-1]
                current = segment_points[0]
                if haversine_meters(
                    previous["lat"],
                    previous["lon"],
                    current["lat"],
                    current["lon"],
                ) < 5:
                    segment_points = segment_points[1:]

            stitched_points.extend(segment_points)
            segment_reports.append({
                key: value
                for key, value in segment.items()
                if key != "points"
            })

        distances = cumulative_distances(stitched_points)
        report["shape_mappings"].append({
            "shape_id": shape_id,
            "segments": segment_reports,
            "point_count": len(stitched_points),
            "distance_km": round(distances[-1] / 1000, 3) if distances else 0,
        })

        for index, point in enumerate(stitched_points):
            shape_rows.append({
                "shape_id": shape_id,
                "shape_pt_lat": round(point["lat"], 7),
                "shape_pt_lon": round(point["lon"], 7),
                "shape_pt_sequence": index + 1,
                "shape_dist_traveled": round(distances[index] / 1000, 3),
            })

    report["used"] = True
    report["generated_shape_points"] = len(shape_rows)
    return shape_rows, report


