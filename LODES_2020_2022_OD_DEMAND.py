#!/usr/bin/env python
# coding: utf-8

import os
import pandas as pd
import matplotlib.pyplot as plt
import csv
from tqdm import tqdm
import time
import requests

# Parameters
STATE = "ny"
YEARS = [2020, 2021, 2022]
JOB_TYPE = "JT00"  # all jobs
BASE_URL = f"https://lehd.ces.census.gov/data/lodes/LODES8/{STATE}/od/{STATE}_od_main_{JOB_TYPE}_{{year}}.csv.gz"

OUTPUT_DIR = "output"
IMAGES_DIR = "images"
OD_MATRIX_FILE_SUM = "OD_demand_LODES.csv"
TOP_N = 15

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

print("Configuration ready.")



# --- SETUP COUNTY FILTERS & MAPPINGS ---
print("\nPreparing NYC county and tract mappings...")

nyc_county_fips = ['36005', '36047', '36061', '36081', '36085']
county_to_borough_digit = {
    '36061': '1',  # Manhattan
    '36005': '2',  # Bronx
    '36047': '3',  # Brooklyn
    '36081': '4',  # Queens
    '36085': '5'   # Staten Island
}

print("NYC county filters and tract mappings initialized.")



# --- LOAD AND PROCESS ONE YEAR AT A TIME ---
print("\nLoading and aggregating LODES data (low-memory mode)...")

# Track total size
total_bytes_downloaded = 0

# Initialize empty aggregation dataframe
od_matrix_total = pd.DataFrame(columns=["origin_tract", "destination_tract", "S000"])

def get_file_size(url):
    """HEAD request to get accurate compressed file size."""
    try:
        r = requests.head(url, timeout=10)
        return int(r.headers.get("Content-Length", 0))
    except:
        return None

for y in YEARS:
    url = BASE_URL.format(year=y)
    print(f"\nLoading {y} from {url}")

    # --- Get File Size ---
    size_bytes = get_file_size(url)
    if size_bytes:
        total_bytes_downloaded += size_bytes
        print(f"   File size: {size_bytes / (1024**3):.3f} GB")
    else:
        print("   File size: Unknown")

    # Timing
    t0 = time.time()

    try:
        # Load compressed CSV in chunks to avoid memory spikes
        chunks = pd.read_csv(url, dtype=str, chunksize=1_000_000)

        year_sum = {}

        # Wrap chunks inside tqdm
        for chunk in tqdm(chunks, desc=f"   Processing {y}", unit="chunk"):

            # Filter to NYC boroughs
            chunk = chunk[
                chunk['h_geocode'].astype(str).str[:5].isin(nyc_county_fips) &
                chunk['w_geocode'].astype(str).str[:5].isin(nyc_county_fips)
            ].copy()

            if chunk.empty:
                continue

            # Convert job count
            chunk['S000'] = (
                pd.to_numeric(chunk['S000'], errors='coerce')
                .fillna(0)
                .astype('int32')
            )

            # Build custom tract IDs
            chunk['origin_tract'] = (
                chunk['h_geocode'].astype(str).str[:5].map(county_to_borough_digit)
                + chunk['h_geocode'].astype(str).str[5:11]
            )
            chunk['destination_tract'] = (
                chunk['w_geocode'].astype(str).str[:5].map(county_to_borough_digit)
                + chunk['w_geocode'].astype(str).str[5:11]
            )

            # Aggregate within chunk
            agg = chunk.groupby(
                ['origin_tract', 'destination_tract']
            )['S000'].sum()

            # Merge chunk sums into running dictionary
            for (o, d), val in agg.items():
                key = (o, d)
                year_sum[key] = year_sum.get(key, 0) + val

        # Append yearly totals into master DataFrame
        df_year = pd.DataFrame(
            [(o, d, v) for (o, d), v in year_sum.items()],
            columns=["origin_tract", "destination_tract", "S000"]
        )
        od_matrix_total = pd.concat([od_matrix_total, df_year], ignore_index=True)

        print(f"   Finished {y}: {len(df_year):,} OD pairs loaded.")
        print(f"   Time: {time.time() - t0:.1f} sec")

    except Exception as e:
        print(f"   Skipping {y} due to error: {e}")

# --- Summary ---
print("\n===============================================================")
print(f"TOTAL DATA DOWNLOADED: {total_bytes_downloaded / (1024**3):.3f} GB")
print("===============================================================")


# In[48]:


# --- COMBINE AND SUM ACROSS ALL YEARS ---
print("\nSumming across all available years (2020–2022)...")

od_matrix_sum = (
    od_matrix_total.groupby(['origin_tract', 'destination_tract'])['S000']
    .sum()
    .reset_index()
    .rename(columns={'S000': 'total_commuters_2020_2022'})
)

print(f"Combined OD matrix ready: {len(od_matrix_sum):,} total OD pairs.")


# In[49]:


# --- SAVE FINAL OUTPUT ---
print("\n Saving output to CSV...")

output_path = os.path.join(OUTPUT_DIR, OD_MATRIX_FILE_SUM)
od_matrix_sum.to_csv(output_path, index=False)

print(f"Saved aggregated OD matrix to: {output_path}")
print("\nPreview:")
print(od_matrix_sum.head())



# --- Filter OD pairs to removeneighbors and self-pairs, then sort output ---

print("\nFiltering OD pairs (drop self and neighbors)")

# Paths
od_path = os.path.join(OUTPUT_DIR, "OD_demand_LODES.csv")
neighbors_csv_path = os.path.join(OUTPUT_DIR, "nyc_tract_neighbors_1mile.csv")
filtered_path = os.path.join(OUTPUT_DIR, "OD_demand_LODES_nonneighbors.csv")

# --- Load OD matrix and normalize IDs ---
df_od = pd.read_csv(od_path, dtype=str)
for col in ("origin_tract", "destination_tract"):
    df_od[col] = df_od[col].astype(str).str.extract(r"(\d+)")[0].str.zfill(7)

print(f"Loaded OD matrix: {len(df_od):,} rows")

# --- Load neighbors into dictionary of sets ---
neighbors_dict = {}
with open(neighbors_csv_path, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        tid = str(row["tract_id"]).zfill(7)
        nlist = [n.strip().zfill(7) for n in row["neighbor_ids"].split(",") if n.strip()]
        neighbors_dict[tid] = set(nlist)

print(f"Loaded {len(neighbors_dict):,} neighbor lists")

# --- Filter out OD pairs that are (a) self-pairs, or (b) within 1 mile ---
mask = []
removed_self = removed_neighbor = 0

for o, d in tqdm(zip(df_od["origin_tract"], df_od["destination_tract"]),
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

# --- Convert commuter counts to numeric and sort descending ---
df_filtered["total_commuters_2020_2022"] = pd.to_numeric(
    df_filtered["total_commuters_2020_2022"], errors="coerce"
)
df_filtered = df_filtered.sort_values("total_commuters_2020_2022", ascending=False)

# --- Save filtered and sorted results ---
df_filtered.to_csv(filtered_path, index=False)
print(f"Saved filtered & sorted file to: {filtered_path}")

# --- Sanity check ---
same_pairs = (df_filtered["origin_tract"] == df_filtered["destination_tract"]).sum()
print(f"Same-tract pairs remaining: {same_pairs}")

print("\n--- Top 10 OD pairs AFTER filtering (sorted by commuters) ---")
print(df_filtered.head(10))



# --- ANALYZE IMPACT OF FILTERING ---
print("\nAnalyzing how much commuter volume was removed...")

# Reload both (in case previous df_od and df_filtered aren't in memory)
df_od = pd.read_csv(os.path.join(OUTPUT_DIR, "OD_demand_LODES.csv"))
df_filtered = pd.read_csv(os.path.join(OUTPUT_DIR, "OD_demand_LODES_nonneighbors.csv"))

# Ensure numeric
df_od['total_commuters_2020_2022'] = pd.to_numeric(df_od['total_commuters_2020_2022'], errors='coerce').fillna(0)
df_filtered['total_commuters_2020_2022'] = pd.to_numeric(df_filtered['total_commuters_2020_2022'], errors='coerce').fillna(0)

# Total commuters before and after
total_before = df_od['total_commuters_2020_2022'].sum()
total_after = df_filtered['total_commuters_2020_2022'].sum()
diff = total_before - total_after
pct_diff = (diff / total_before) * 100

print(f"Total commuters before: {total_before:,.0f}")
print(f"Total commuters after:  {total_after:,.0f}")
print(f"Removed commuters:      {diff:,.0f} ({pct_diff:.2f}% of total)")

# --- Top 10 OD pairs before and after ---
top_before = df_od.sort_values('total_commuters_2020_2022', ascending=False).head(10)
top_after = df_filtered.sort_values('total_commuters_2020_2022', ascending=False).head(10)

print("\n--- Top 10 OD pairs BEFORE filtering ---")
print(top_before[['origin_tract', 'destination_tract', 'total_commuters_2020_2022']])

print("\n--- Top 10 OD pairs AFTER filtering ---")
print(top_after[['origin_tract', 'destination_tract', 'total_commuters_2020_2022']])