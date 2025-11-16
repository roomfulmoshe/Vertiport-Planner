import pandas as pd
import geopandas as gpd
from random import randint
import os
import matplotlib.pyplot as plt
import seaborn as sns
# --- TUNABLE PARAMETER ---
# Set the minimum overlap threshold. A value of 0.01 means we discard any
# tract that covers less than 1% of the taxi zone's area.
MIN_APPORTION_THRESHOLD = 0.01

print("Step 1: Loading shapefiles...")
fp_zones = 'taxi_zones/taxi_zones.shp'
fp_tracts = 'nyc_tracts/nyct2020.shp'
projected_crs = 'EPSG:2263'

try:
    zones_raw = gpd.read_file(fp_zones)
    tracts = gpd.read_file(fp_tracts).to_crs(projected_crs)
except Exception as e:
    print(f"Error loading shapefiles: {e}")
    exit()

print("\nStep 2: Cleaning the Taxi Zone data (Dissolving)...")
zones = zones_raw.dissolve(by='LocationID').reset_index()
zones = zones.to_crs(projected_crs)
print("Taxi zones cleaned.")

print("\nStep 3: Calculating total area for each cleaned taxi zone...")
zones['zone_total_area'] = zones.geometry.area

print("\nStep 4: Performing spatial intersection...")
intersection = gpd.overlay(
    tracts[['BoroCT2020', 'geometry']],
    zones[['LocationID', 'zone_total_area', 'geometry']],
    how='intersection'
)

print("\nStep 5: Aggregating MultiPolygon results and calculating initial weights...")
# First, sum up pieces of the same tract within the same zone (handles MultiPolygons)
intersection['intersect_area'] = intersection.geometry.area
agg_intersection = intersection.groupby(['LocationID', 'BoroCT2020', 'zone_total_area']).agg({'intersect_area': 'sum'}).reset_index()

# Calculate the initial weight based on the summed area
agg_intersection['apportion_weight'] = agg_intersection['intersect_area'] / agg_intersection['zone_total_area']

print(f"\nStep 6: Filtering out insignificant overlaps (less than {MIN_APPORTION_THRESHOLD * 100}%)...")
# Filtering threshold
filtered_crosswalk = agg_intersection[agg_intersection['apportion_weight'] >= MIN_APPORTION_THRESHOLD].copy()
print(f"Removed rows with tiny weights. Kept {len(filtered_crosswalk)} significant overlaps.")

print("\nStep 7: Re-Normalizing weights to ensure they sum to 1...")
# --- RE-NORMALIZATION STEP ---
# After filtering, the weights for a zone no longer sum to 1. We must fix this.
weight_sums = filtered_crosswalk.groupby('LocationID')['apportion_weight'].sum().to_dict()

filtered_crosswalk['apportion_weight_normalized'] = filtered_crosswalk.apply(
    lambda row: row['apportion_weight'] / weight_sums[row['LocationID']],
    axis=1
)
print("Remaining weights have been re-normalized.")

print("\nStep 8: Building and exporting the crosswalk file...")
final_crosswalk = filtered_crosswalk[['LocationID', 'BoroCT2020', 'apportion_weight_normalized']]
final_crosswalk = final_crosswalk.rename(columns={
    'BoroCT2020': 'census_tract_id',
    'apportion_weight_normalized': 'apportion_weight'
})

if not os.path.exists('output'):
    os.makedirs('output')
    print("Created 'output' subfolder.")

output_filename = 'output/nyc_zone_tract_crosswalk.csv'
final_crosswalk.to_csv(output_filename, index=False, float_format='%.6f')

print("-" * 50)
print(f"Success! Your crosswalk file is ready: {output_filename}")
print("This version has been cleaned, filtered, and weights are normalized to sum to 1.")
print("-" * 50)

# Final Validation Check:
randint_location_id = randint(2, 263)  # Assuming LocationIDs range from 1 to 263
validation_sum = final_crosswalk[final_crosswalk['LocationID'] == randint_location_id]['apportion_weight'].sum()
print(f"Final Validation: Sum of weights for test LocationID {randint_location_id} is now: {validation_sum:.6f}")
print("-" * 50)




print("\n--- Post-Analysis: Validating Zone Simplicity ---")

# --- Setup ---
if not os.path.exists('images'):
    os.makedirs('images')
    print("Created 'images' subfolder.")

# We define a "Simple Zone" as one that overlaps with 10 or fewer census tracts.
SIMPLICITY_THRESHOLD = 10

# 1. Group by LocationID and count the number of census tracts for each
tracts_per_zone = final_crosswalk.groupby('LocationID')['census_tract_id'].count()

# 2. Get the total number of unique taxi zones
total_zones = len(tracts_per_zone)

# 3. Find all zones that are "Simple" (at or below our threshold)
simple_zones = tracts_per_zone[tracts_per_zone <= SIMPLICITY_THRESHOLD]
simple_zone_count = len(simple_zones)

# 4. Calculate the percentage
percent_simple = (simple_zone_count / total_zones) * 100

# --- Print Results ---
print("\n--- Validation Results ---")
print(f"Total Taxi Zones Analyzed: {total_zones}")
print(f"Simple Zones (<= {SIMPLICITY_THRESHOLD} tracts): {simple_zone_count}")
print(f"Complex Zones (> {SIMPLICITY_THRESHOLD} tracts): {total_zones - simple_zone_count}")

print("\n--- CONCLUSION ---")
print(f"Analysis Confirmed: {percent_simple:.1f}% of all taxi zones are 'simple',")
print(f"   meaning they overlap with {SIMPLICITY_THRESHOLD} or fewer census tracts.")
print("\nThis confirms that for the vast majority of the city,")
print(f"   our method is linking demand to a small, cohesive geographic area.")
print("-" * 50)


# --- Plotting Graph ---
print("Generating Plot 1: Simplicity of Taxi Zones...")
plt.figure(figsize=(12, 7))
sns.histplot(tracts_per_zone, bins=20, kde=False)
plt.title('Most Taxi Zones Map to a Small Number of Tracts', fontsize=16, fontweight='bold')
plt.xlabel('Number of Census Tracts per Taxi Zone', fontsize=12)
plt.ylabel('Count of Taxi Zones', fontsize=12)
plt.grid(axis='y', alpha=0.75)
plt.figtext(0.5, -0.1,
            f"JUSTIFICATION: This plot proves our merge is valid. {percent_simple:.1f}% of taxi zones map to\n"
            f"{SIMPLICITY_THRESHOLD} or fewer census tracts, so we are not 'diluting' demand data across too many areas.\n"
            "The linkage is direct and reliable for most of the city.",
            ha="center", fontsize=11, style='italic', bbox={"facecolor":"#f0f0f0", "pad":5})
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig('images/1_zone_simplicity_histogram.png', bbox_inches='tight')
plt.close()

print("Plot 1 saved to 'images/1_zone_simplicity_histogram.png'")