#!/usr/bin/env python
# coding: utf-8

# | Task                | Complexity     | Runtime     | Result size          |
# |----------------------|----------------|--------------|----------------------|
# | Build index          | O(N log N)     | <1 s         | in-memory            |
# | Precompute neighbors | O(N × K)       | ~1–2 min     | ~2–3 MB CSV          |
# | Lookup from file     | O(1)           | microseconds | dictionary lookup    |
#


import geopandas as gpd
from shapely.geometry import Polygon
import pandas as pd
from tqdm import tqdm  # optional progress bar

gdf = gpd.read_file("nyc_tracts/nyc_tracts.json")
if gdf.crs is None:
    gdf.set_crs(epsg=2263, inplace=True)

# Keep only needed columns
gdf = gdf[["GEOID", "geometry"]].rename(columns={"GEOID": "tract_id"})

# Shorten to last 7 digits (strip '36' state and '061' county code)
gdf["tract_id"] = gdf["tract_id"].str[-7:]
gdf.reset_index(drop=True, inplace=True)

print("Tracts loaded:", len(gdf))




sindex = gdf.sindex



def get_neighbors(tract_geom, sindex, gdf, X_miles=1):
    buffer_geom = tract_geom.buffer(X_miles * 5280)
    candidate_idx = list(sindex.intersection(buffer_geom.bounds))
    candidates = gdf.iloc[candidate_idx]
    nearby = candidates[candidates.intersects(buffer_geom)]
    return nearby["tract_id"].tolist()

neighbors = {}

for idx, row in tqdm(gdf.iterrows(), total=len(gdf)):
    tract_id = row["tract_id"]
    neighbors[tract_id] = get_neighbors(row["geometry"], sindex, gdf, X_miles=1)


# Convert to DataFrame for easier export
df_neighbors = pd.DataFrame([
    {"tract_id": tid, "neighbor_ids": ",".join(nlist)}
    for tid, nlist in neighbors.items()
])

df_neighbors.to_csv("output/nyc_tract_neighbors_1mile.csv", index=False)
print("Saved to output/nyc_tract_neighbors_1mile.csv")


# neighbors_df = pd.read_csv("nyc_tract_neighbors_1mile.csv")

# # Turn back into dict for fast lookups
# neighbors_dict = {
#     row["tract_id"]: row["neighbor_ids"].split(",")
#     for _, row in neighbors_df.iterrows()
# }

# # Example usage
# neighbors_dict["1000100"]




import json
with open("output/nyc_tract_neighbors_1mile.json", "w") as f:
    json.dump(neighbors, f)



import geopandas as gpd
import pandas as pd
import json

# Load the original GeoJSON
gdf = gpd.read_file("nyc_tracts/nyc_tracts.json")
if gdf.crs is None:
    gdf.set_crs(epsg=2263, inplace=True)

# Normalize tract_id the same way you used in precomputation
gdf["tract_id"] = gdf["GEOID"].str[-7:]

# Load your CSV and JSON
neighbors_csv = pd.read_csv("output/nyc_tract_neighbors_1mile.csv")
with open("output/nyc_tract_neighbors_1mile.json") as f:
    neighbors_json = json.load(f)

print(f"GeoJSON tracts: {len(gdf)}")
print(f"CSV entries: {len(neighbors_csv)}")
print(f"JSON entries: {len(neighbors_json)}")



neighbors_csv["neighbor_count"] = neighbors_csv["neighbor_ids"].apply(lambda x: len(x.split(",")))

print("Average neighbors per tract:", neighbors_csv["neighbor_count"].mean())
print("Min neighbors:", neighbors_csv["neighbor_count"].min())
print("Max neighbors:", neighbors_csv["neighbor_count"].max())

neighbors_csv["neighbor_count"].describe()



neighbors_csv.sample(5)



tid = neighbors_csv.iloc[7]["tract_id"]
print(tid)
neighbors_csv.loc[neighbors_csv["tract_id"] == tid, "neighbor_ids"].values[0]


asym = []
for a, neighs in neighbors_json.items():
    for b in neighs:
        if b not in neighbors_json or a not in neighbors_json[b]:
            asym.append((a, b))

print(f"Asymmetric pairs: {len(asym)}")
if asym:
    print("Examples:", asym[:10])