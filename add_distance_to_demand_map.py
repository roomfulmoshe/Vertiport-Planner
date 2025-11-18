import pandas as pd
import geopandas as gpd
from itertools import product
import math
import sys

df = pd.read_csv("output/Universal_Demand_Map.csv", dtype=str)
gdf = gpd.read_file("nyc_tracts/nyct2020.shp")

gdf = gdf[["BoroCT2020", "geometry"]].copy()
gdf["BoroCT2020"] = gdf["BoroCT2020"].astype(str)
if gdf.crs is None:
    print("shapefile has no crs, attempting to assume epsg:4326")
    gdf = gdf.set_crs(epsg=4326, allow_override=True)
else:
    gdf = gdf.to_crs(epsg=4326)
gdf["centroid"] = gdf.geometry.centroid
centroids = {k: (pt.x, pt.y) for k, pt in zip(gdf["BoroCT2020"], gdf["centroid"]) if pt is not None}

sample = list(centroids.items())[:10]
print("first 10 centroids:", sample, file=sys.stderr)

df["origin_tract"] = df["origin_tract"].astype(str)
df["destination_tract"] = df["destination_tract"].astype(str)

origins = sorted(df["origin_tract"].unique())
dests = sorted(df["destination_tract"].unique())
all_pairs = set(product(origins, dests))
existing_pairs = set(zip(df["origin_tract"], df["destination_tract"]))
missing = all_pairs - existing_pairs

if missing:
    zero_cols = [c for c in df.columns if c not in ["origin_tract", "destination_tract", "distance_km"]]
    add_rows = []
    for o, d in missing:
        row = {"origin_tract": o, "destination_tract": d}
        for c in zero_cols:
            row[c] = 0
        row["distance_km"] = ""
        add_rows.append(row)
    df = pd.concat([df, pd.DataFrame(add_rows)], ignore_index=True)

def haversine(lon1, lat1, lon2, lat2):
    if None in (lon1, lat1, lon2, lat2):
        return None
    R = 6371.0
    dlon = math.radians(lon2 - lon1)
    dlat = math.radians(lat2 - lat1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def row_distance(r):
    o = r["origin_tract"]
    d = r["destination_tract"]
    p1 = centroids.get(o)
    p2 = centroids.get(d)
    if p1 is None or p2 is None:
        return ""
    return haversine(p1[0], p1[1], p2[0], p2[1])

df["distance_km"] = df.apply(row_distance, axis=1)
df.to_csv("output/Universal_Demand_Map.csv", index=False)
