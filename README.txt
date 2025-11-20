NYC Vertiport Site Selection - Data Pipeline

A complete data processing pipeline for analyzing potential vertiport
locations in New York City using taxi/ride-share demand, commuter flows,
and demographic data.

Table of Contents

-   Overview
-   Complete Setup from Scratch
-   Pipeline Stages
-   Visualization
-   Output Files
-   Troubleshooting

------------------------------------------------------------------------

Overview

This pipeline processes multiple geospatial and transportation datasets
to identify optimal vertiport locations in NYC. It combines:

-   TLC Taxi/Ride-share data (2020-2024) - Trip records showing demand
    patterns
-   LODES Commuter data (2020-2022) - Census workplace flows
-   ACS Demographics - Population and income data
-   Geospatial crosswalks - Mapping between taxi zones and census tracts

------------------------------------------------------------------------

Complete Setup from Scratch

Follow these steps exactly to set up and run the entire pipeline from a
clean system.

Step 1: Clone the Repository (optional if not downloaded)

    git clone https://github.com/roomfulmoshe/Vertiport-Planner.git
    cd Vertiport-Planner

Step 2: Create Python Virtual Environment

On macOS/Linux:

    python3 -m venv venv
    source venv/bin/activate

On Windows:

    python -m venv venv
    venv\Scripts\activate

Step 3: Install ALL Required Packages

    This project uses python 3.11
    # Upgrade pip first
    pip install --upgrade pip

    # Install all dependencies including notebook
    pip install -r requirements.txt

    # Verify installation
    python -c "import geopandas, pandas, numpy; print('✓ All packages installed successfully')"

Step 4: Create Required Directories

    mkdir -p taxi_zones nyc_tracts output

Step 5: Download Geographic Base Files

Download NYC Taxi Zones:

    cd taxi_zones
    curl -O https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip
    unzip taxi_zones.zip
    rm taxi_zones.zip
    cd ..

Download NYC Census Tracts:

    cd nyc_tracts
    curl -O https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/census-tracts/nyct2020_25c.zip
    unzip nyct2020_25c.zip
    mv nyct2020_25c/* .
    rmdir nyct2020_25c
    rm nyct2020_25c.zip
    cd ..

Step 6: Create GeoJSON File (Required)

IMPORTANT: After downloading the shapefiles, create the GeoJSON file
needed for Stage 2 and visualizations:

    python -c "import geopandas as gpd; gdf = gpd.read_file('nyc_tracts/nyct2020.shp'); gdf.to_file('nyc_tracts/nyc_tracts.json', driver='GeoJSON'); print('✓ GeoJSON created successfully')"

This step is required before running Stage 2
(GenerateNeighborsCSVJSON.py).

Step 7: Verify Setup

    # Check that all files are in place
    ls taxi_zones/*.shp
    ls nyc_tracts/*.shp
    ls nyc_tracts/*.json
    ls output/

------------------------------------------------------------------------

Pipeline Stages

Run these stages in order:

Stage 1: Geospatial Crosswalk

    python geospatial_join.py

Runtime: ~2 minutes | Output: output/nyc_zone_tract_crosswalk.csv

Stage 2: Generate Neighbors

    python GenerateNeighborsCSVJSON.py

Runtime: ~1 minute | Output: output/nyc_tract_neighbors_1mile.csv

**Requires GeoJSON file from Step 6

Stage 3: TLC Taxi Data (Optional)

    python TLC_2020_2024_OD_DEMAND.py

Runtime: ~20 minutes | Download: ~10GB | Output:
output/OD_demand_TLC.csv

Stage 4: LODES Commuter Data

    python LODES_2020_2022_OD_DEMAND.py

Runtime: ~3 minutes | Download: ~120MB | Output:
output/OD_demand_LODES_nonneighbors.csv

Stage 5: Universal Demand (Requires Stage 3)

    python UniversalDemand.py

Runtime: ~2 minutes | Output: output/OD_demand_universal.csv

Stage 5.1: Universald Demand Part II
    python add_distance_to_demand_map.py

Runtime: ~5 minutes | Output: output/OD_demand_universal.csv (modifies it)

Stage 6: Demographics

    python ACS_demographics_tract_level.py

Runtime: ~2 minutes | Output: output/nyc_census_tract_demographics.csv

------------------------------------------------------------------------

Visualization

Option 1: View HTML Visualizations (Recommended)

Using Python HTTP Server:

    python -m http.server 8000

Then open in browser: - http://localhost:8000/visualize_greedy.html

Using VS Code Live Server: 1. Install “Live Server” extension 2.
Right-click HTML file → “Open with Live Server”

Option 2: Run Jupyter Notebooks

    jupyter notebook

Open any .ipynb file and run cells with Shift+Enter or “Run All”

------------------------------------------------------------------------

Output Files

  ------------------------------------------------------------------------------------------
  File                                Size              Description
  ----------------------------------- ----------------- ------------------------------------
  nyc_zone_tract_crosswalk.csv        47KB              Zone-to-tract mapping

  nyc_tract_neighbors_1mile.csv       1.0MB             Tract adjacency

  OD_demand_LODES_nonneighbors.csv    31MB              Commuter flows

  nyc_census_tract_demographics.csv   52KB              Demographics

  OD_demand_TLC_nonneighbors.csv                   ~500MB            Taxi demand (if Stage 3 run)

  OD_demand_universal.csv             ~500MB            Combined demand (if Stage 5 run)
  ------------------------------------------------------------------------------------------

------------------------------------------------------------------------

Troubleshooting

Issue: “FileNotFoundError: nyc_tracts/nyc_tracts.json”

    python -c "import geopandas as gpd; gdf = gpd.read_file('nyc_tracts/nyct2020.shp'); gdf.to_file('nyc_tracts/nyc_tracts.json', driver='GeoJSON')"

Issue: Import errors

    source venv/bin/activate
    pip install -r requirements.txt
    pip install jupyter notebook

Issue: Visualizations not loading

    # Use HTTP server, not file://
    python -m http.server 8000

------------------------------------------------------------------------

Quick Reference: Complete Workflow

    # Clone and setup
    git clone https://github.com/roomfulmoshe/Vertiport-Planner.git
    cd Vertiport-Planner
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install jupyter notebook

    # Create directories
    mkdir -p taxi_zones nyc_tracts output

    # Download data
    cd taxi_zones && curl -O https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip && unzip taxi_zones.zip && rm taxi_zones.zip && cd ..
    cd nyc_tracts && curl -O https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/census-tracts/nyct2020_25c.zip && unzip nyct2020_25c.zip && mv nyct2020_25c/* . && rmdir nyct2020_25c && rm nyct2020_25c.zip && cd ..

    # CREATE GEOJSON (IMPORTANT!)
    python -c "import geopandas as gpd; gdf = gpd.read_file('nyc_tracts/nyct2020.shp'); gdf.to_file('nyc_tracts/nyc_tracts.json', driver='GeoJSON'); print('✓ GeoJSON created')"

    # Run pipeline
    python geospatial_join.py
    python GenerateNeighborsCSVJSON.py
    python LODES_2020_2022_OD_DEMAND.py
    python ACS_demographics_tract_level.py

    # View visualizations
    python -m http.server 8000
    # Open: http://localhost:8000/visualize_greedy.html

------------------------------------------------------------------------

Team: Moshe Shtaygrud, Nora A Fahim, Leonel A Castillo, Mohamed Rafee Kaza Kamaludeen, Emily G O'Connell, Allaa H Sharif
Last Updated: November 2025
