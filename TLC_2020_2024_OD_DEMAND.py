#!/usr/bin/env python
# coding: utf-8

import pandas as pd
import os
import time
import requests
import pyarrow.parquet as pq
from io import BytesIO
import numpy as np
import matplotlib.pyplot as plt
import csv
from tqdm import tqdm

# ======================================================================
# 1. CONFIGURATION
# ======================================================================

CROSSWALK_FILE = "output/nyc_zone_tract_crosswalk.csv"
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "OD_demand_TLC.csv")

total_bytes_downloaded = 0

COLUMNS_TO_LOAD = [
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "trip_distance",
    "passenger_count",
    "total_amount",
    "PULocationID",
    "DOLocationID",
]

MIN_DISTANCE_MILES = 2.0
MIN_DURATION_MINUTES = 5.0
MAX_DURATION_MINUTES = 240
MIN_PASSENGERS = 1
MIN_FARE = 2.5
VALID_ZONE_RANGE = (1, 263)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Connection": "keep-alive",
}

# ======================================================================
# 2. HELPERS
# ======================================================================

def get_file_size_head(url):
    """Accurate size using HEAD request."""
    try:
        r = requests.head(url, headers=HEADERS, timeout=10)
        if "Content-Length" in r.headers:
            return int(r.headers["Content-Length"])
    except:
        pass
    return None


def stream_parquet_in_chunks(url):
    """
    Downloads the full parquet and yields each row group.
    """
    global total_bytes_downloaded

    response = requests.get(url, headers=HEADERS, stream=True, timeout=60)
    response.raise_for_status()

    content = BytesIO(response.content)
    total_bytes_downloaded += len(response.content)

    parquet_file = pq.ParquetFile(content)

    for rg in range(parquet_file.num_row_groups):
        yield parquet_file.read_row_group(rg, columns=COLUMNS_TO_LOAD).to_pandas()


# ======================================================================
# 3. URL LIST
# ======================================================================

print("Step 1: Generating data URLs...")
dates = pd.date_range("2020-01-01", "2024-12-01", freq="MS")

TLC_URLS = [
    f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{d.strftime('%Y-%m')}.parquet"
    for d in dates
]

print(f"Generated {len(TLC_URLS)} URLs")
print("-" * 50)

# ======================================================================
# 4. LOAD CROSSWALK
# ======================================================================

print(f"Step 2: Loading crosswalk '{CROSSWALK_FILE}'...")
df_crosswalk = pd.read_csv(CROSSWALK_FILE)

pickup_crosswalk = df_crosswalk.rename(columns={
    "LocationID": "PULocationID",
    "census_tract_id": "pickup_tract_id",
    "apportion_weight": "pickup_weight",
})

dropoff_crosswalk = df_crosswalk.rename(columns={
    "LocationID": "DOLocationID",
    "census_tract_id": "dropoff_tract_id",
    "apportion_weight": "dropoff_weight",
})

print("Crosswalk loaded")
print("-" * 50)

# ======================================================================
# 5. PROCESS MONTH-BY-MONTH (NOW WITH TQDM BAR)
# ======================================================================

print(f"Step 3: Processing {len(TLC_URLS)} monthly files...\n")

all_months = []
global_start = time.time()

for i, url in enumerate(tqdm(TLC_URLS, desc="Monthly Files Processed")):
    label = url.split("/")[-1]
    print(f"\n  ({i+1}/{len(TLC_URLS)}) {label}")
    month_start = time.time()

    # -------- 1. Get size via HEAD --------
    size = get_file_size_head(url)
    if size:
        print(f"       File size: {size / (1024**3):.3f} GB")
    else:
        print("       File size: Unknown (HEAD failed)")

    od_chunks = []

    # -------- 2. Stream row-groups --------
    try:
        for chunk_df in stream_parquet_in_chunks(url):

            chunk_df["tpep_pickup_datetime"] = pd.to_datetime(
                chunk_df["tpep_pickup_datetime"], errors="coerce")
            chunk_df["tpep_dropoff_datetime"] = pd.to_datetime(
                chunk_df["tpep_dropoff_datetime"], errors="coerce")

            chunk_df["duration_min"] = (
                chunk_df["tpep_dropoff_datetime"] - chunk_df["tpep_pickup_datetime"]
            ).dt.total_seconds() / 60

            df_filtered = chunk_df[
                (chunk_df["passenger_count"] >= MIN_PASSENGERS) &
                (chunk_df["total_amount"] > MIN_FARE) &
                (chunk_df["PULocationID"] != chunk_df["DOLocationID"]) &
                (chunk_df["PULocationID"].between(*VALID_ZONE_RANGE)) &
                (chunk_df["DOLocationID"].between(*VALID_ZONE_RANGE)) &
                (chunk_df["trip_distance"] > MIN_DISTANCE_MILES) &
                (chunk_df["duration_min"].between(MIN_DURATION_MINUTES, MAX_DURATION_MINUTES))
            ][["PULocationID", "DOLocationID"]]

            if df_filtered.empty:
                continue

            merged = df_filtered.merge(pickup_crosswalk, on="PULocationID", how="inner")
            merged = merged.merge(dropoff_crosswalk, on="DOLocationID", how="inner")

            merged["trip_fraction"] = merged["pickup_weight"] * merged["dropoff_weight"]

            od_chunks.append(
                merged.groupby(["pickup_tract_id", "dropoff_tract_id"])["trip_fraction"]
                .sum()
                .reset_index()
            )

        if od_chunks:
            month_df = pd.concat(od_chunks)
            all_months.append(month_df)
            print(f"       ✔ Completed month: {len(month_df)} OD pairs")
        else:
            print("       ✔ Completed month: (no qualifying trips)")

    except Exception as e:
        print(f"      Error processing: {e}")

    # ----- Month time summary -----
    month_end = time.time()
    print(f"       Time: {(month_end - month_start):.1f} sec")

# ======================================================================
# 6. FINAL OD AGGREGATION
# ======================================================================

print("\nStep 4: Combining all months...")

if not all_months:
    print("No months were processed successfully.")
else:
    df_all = pd.concat(all_months)

    final = (
        df_all.groupby(["pickup_tract_id", "dropoff_tract_id"])["trip_fraction"]
        .sum()
        .reset_index()
    )

    final.rename(columns={"trip_fraction": "total_trips"}, inplace=True)
    final["total_trips"] = final["total_trips"].round(4)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"Saved final OD matrix → {OUTPUT_FILE}\n")
    print(final.sort_values("total_trips", ascending=False).head(10))

# ======================================================================
# 7. SUMMARY
# ======================================================================

print("======================================================")
print(f"TOTAL BYTES DOWNLOADED: {total_bytes_downloaded / (1024**3):.3f} GB")
print(f"TOTAL TIME: {(time.time() - global_start)/60:.1f} min")
print("======================================================")



OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

input_path = os.path.join(OUTPUT_DIR, "OD_demand_TLC.csv")
neighbors_csv_path = os.path.join(OUTPUT_DIR, "nyc_tract_neighbors_1mile.csv")
filtered_path = os.path.join(OUTPUT_DIR, "OD_demand_TLC_nonneighbors.csv")
df_od = pd.read_csv(input_path, dtype=str)

for col in ("pickup_tract_id", "dropoff_tract_id"):
    df_od[col] = df_od[col].astype(str).str.extract(r"(\d+)")[0].str.zfill(7)

print(f"Loaded OD dataset: {len(df_od):,} rows")
df_od.head()


neighbors_dict = {}
with open(neighbors_csv_path, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        tid = str(row["tract_id"]).zfill(7)
        nlist = [n.strip().zfill(7) for n in row["neighbor_ids"].split(",") if n.strip()]
        neighbors_dict[tid] = set(nlist)

print(f"Loaded {len(neighbors_dict):,} neighbor tracts from lookup table.")
mask = []
removed_self = removed_neighbor = 0

for o, d in tqdm(zip(df_od["pickup_tract_id"], df_od["dropoff_tract_id"]),
                 total=len(df_od), desc="Filtering OD pairs"):
    if o == d:
        removed_self += 1
        mask.append(False)
    elif d in neighbors_dict.get(o, set()):
        removed_neighbor += 1
        mask.append(False)
    else:
        mask.append(True)

df_filtered = df_od[mask].reset_index(drop=True)

print(f"Removed self-pairs: {removed_self:,}")
print(f"Removed neighbor pairs: {removed_neighbor:,}")
print(f"Kept {len(df_filtered):,} of {len(df_od):,} OD rows")
df_filtered["total_trips"] = pd.to_numeric(df_filtered["total_trips"], errors="coerce")
df_filtered = df_filtered.sort_values("total_trips", ascending=False)

df_filtered.to_csv(filtered_path, index=False)
print(f"Saved filtered & sorted file to: {filtered_path}")



# --- 1. LOAD THE FINAL DATASET ---
FILE_TO_ANALYZE = os.path.join(OUTPUT_DIR, "OD_demand_TLC_nonneighbors.csv")

print(f"Loading '{FILE_TO_ANALYZE}'...")
try:
    df_od = pd.read_csv(FILE_TO_ANALYZE)
    print(f"Success! Loaded file with {len(df_od)} unique O-D pairs.")
    print("\n--- Data Head ---")
    print(df_od.head())

except FileNotFoundError:
    print(f"ERROR: Could not find the file '{FILE_TO_ANALYZE}'.")
    print("Please make sure the previous script cell ran successfully and created the file.")



# --- 2. GET BASIC STATISTICS ---
print("--- Statistics for 'total_trips' (2020-2024) ---")

# Use describe() with percentiles to see the long-tail distribution
# We add 90%, 95%, 99%, and 99.9% to see how skewed the data is
stats = df_od['total_trips'].describe(percentiles=[.25, .5, .75, .90, .95, .99, .999])
print(stats)

print(f"\n--- Key Insights ---")
print(f"Total O-D Pairs:     {stats['count']:,.0f}")
print(f"Average Trips/Pair:  {stats['mean']:.2f}")
print(f"Median Trips/Pair:   {stats['50%']:.2f} (Half of all routes have fewer than this many trips!)")
print(f"Top 1% of Routes:    At least {stats['99%']:.2f} trips")
print(f"Top 0.1% of Routes:  At least {stats['99.9%']:.2f} trips")


# --- 3. ANALYSIS 1: TOP 20 O-D ROUTES ---
TOP_N = 20

# Sort the entire DataFrame to find the 20 highest-demand routes
df_top_routes = df_od.sort_values(by='total_trips', ascending=False).head(TOP_N)

# Create a human-readable 'route' column for plotting
df_top_routes['route'] = df_top_routes['pickup_tract_id'].astype(str) + '  →  ' + df_top_routes['dropoff_tract_id'].astype(str)

# Sort ascending for the horizontal bar chart (so top item is on top)
df_top_routes.sort_values(by='total_trips', ascending=True, inplace=True)

# --- Plot ---
plt.figure(figsize=(12, 10))
plt.barh(df_top_routes['route'], df_top_routes['total_trips'], color='skyblue')
plt.title(f'Top {TOP_N} Busiest O-D Routes by Census Tract (2020-2024)', fontsize=16)
plt.xlabel('Total Apportioned Trips (5-Year Total)', fontsize=12)
plt.ylabel('Origin → Destination Tract', fontsize=12)
plt.tight_layout()
plt.show()

print("\n--- Top 10 Routes ---")
print(df_top_routes.sort_values(by='total_trips', ascending=False)[['route', 'total_trips']].head(10))

