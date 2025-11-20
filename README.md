# NYC Vertiport Site Selection — Data Processing Pipeline

A comprehensive, end-to-end geospatial and transportation analytics pipeline for evaluating potential **vertiport** (urban air mobility) locations across New York City.  
This system integrates taxi trip demand, commuting flows, demographic patterns, and geospatial adjacency relationships to support evidence-driven infrastructure planning.

---

## Table of Contents

- [Overview](#overview)
- [Complete Setup from Scratch](#complete-setup-from-scratch)
- [Pipeline Stages](#pipeline-stages)
- [Visualization](#visualization)
- [Output Files](#output-files)
- [Troubleshooting](#troubleshooting)
- [Quick Reference: Complete Workflow](#quick-reference-complete-workflow)
- [Team & Attribution](#team--attribution)

---

## Overview

This pipeline processes multiple NYC transportation and demographic datasets to evaluate vertiport suitability at the census-tract and taxi-zone levels.

The workflow integrates:

- **TLC Taxi & Ride-Share Trips (2020–2024)**  
  High-resolution origin–destination trip demand patterns across yellow TLC Taxi Data.

- **LODES Commuter Data (2020–2022)**  
  Census-based home-to-work commuting flows, capturing large-scale mobility behaviors.

- **ACS Demographic Information**  
  Population, income, and density indicators for contextualizing demand and equity.

- **Geospatial Crosswalks & Adjacency Models**  
  Automated mapping between taxi zones and census tracts, as well as tract-level 1-mile neighbors.

---

## Complete Setup from Scratch

Follow these steps. These commands are expected to run without modification.

### **Step 1 — Clone the Repository**

```bash
git clone https://github.com/roomfulmoshe/Vertiport-Planner.git
cd Vertiport-Planner
```

### **Step 2 — Create Python Virtual Environment**

**macOS/Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows**

```bash
python -m venv venv
venv\Scripts\activate
```

### **Step 3 — Install ALL Required Packages**

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install jupyter notebook

python -c "import geopandas, pandas, numpy; print('✓ All packages installed successfully')"
```

### **Step 4 — Create Required Directories**

```bash
mkdir -p taxi_zones nyc_tracts output
```

### **Step 5 — Download Geographic Base Files**

#### **NYC Taxi Zones**

```bash
cd taxi_zones
curl -O https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip
unzip taxi_zones.zip
rm taxi_zones.zip
cd ..
```

#### **NYC Census Tracts**

```bash
cd nyc_tracts
curl -O https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/census-tracts/nyct2020_25c.zip
unzip nyct2020_25c.zip
mv nyct2020_25c/* .
rmdir nyct2020_25c
rm nyct2020_25c.zip
cd ..
```

### **Step 6 — Create Required GeoJSON File**

```bash
python -c "import geopandas as gpd; gdf = gpd.read_file('nyc_tracts/nyct2020.shp'); gdf.to_file('nyc_tracts/nyc_tracts.json', driver='GeoJSON'); print('✓ GeoJSON created successfully')"
```

### **Step 7 — Verify Setup**

```bash
ls taxi_zones/*.shp
ls nyc_tracts/*.shp
ls nyc_tracts/*.json
ls output/
```

---

## Pipeline Stages

### **Stage 1 — Geospatial Crosswalk**

```bash
python geospatial_join.py
```

**Output:** `output/nyc_zone_tract_crosswalk.csv`

---

### **Stage 2 — Generate Neighbors**

```bash
python GenerateNeighborsCSVJSON.py
```

**Output:** `output/nyc_tract_neighbors_1mile.csv`

---

### **Stage 3 — TLC Taxi Demand**

```bash
python TLC_2020_2024_OD_DEMAND.py
```

**Output:** `output/OD_demand_TLC.csv` and `output/OD_demand_TLC_nonneighbors.csv`

---

### **Stage 4 — LODES Commuter Demand**

```bash
python LODES_2020_2022_OD_DEMAND.py
```

**Output:** `output/OD_demand_LODES_nonneighbors.csv`

---

### **Stage 5 — Universal Demand**

```bash
python UniversalDemand.py
```

**Output:** `output/Universal_Demand_Map.csv`

### **Stage 5.1 — Universal Demand Part II**

```bash
python add_distance_to_demand_map.py
```

---

### **Stage 6 — Demographics**

```bash
python ACS_demographics_tract_level.py
```

**Output:** `output/nyc_census_tract_demographics.csv`

---

## Visualization

### **Option 1 — HTML Visualizations**

```bash
python -m http.server 8000
```

Open:

- http://localhost:8000/visualize_greedy.html

### **Option 2 — Jupyter Notebooks**

```bash
jupyter notebook
```

---

## Output Files

| File                              | Size   | Description           |
| --------------------------------- | ------ | --------------------- |
| nyc_zone_tract_crosswalk.csv      | 47KB   | Zone-to-tract mapping |
| nyc_tract_neighbors_1mile.csv     | 1MB    | Tract adjacency       |
| OD_demand_LODES_nonneighbors.csv  | 31MB   | Commuter flows        |
| nyc_census_tract_demographics.csv | 52KB   | Demographics          |
| OD_demand_TLC_nonneighbors.csv    | ~500MB | Taxi demand           |
| OD_demand_universal.csv           | ~500MB | Combined OD demand    |

---

## Troubleshooting

### Missing GeoJSON

```bash
python -c "import geopandas as gpd; gdf = gpd.read_file('nyc_tracts/nyct2020.shp'); gdf.to_file('nyc_tracts/nyc_tracts.json', driver='GeoJSON')"
```

### Import Errors

```bash
source venv/bin/activate
pip install -r requirements.txt
pip install jupyter notebook
```

### Visualizations Not Loading

```bash
python -m http.server 8000
```

---

## Quick Reference: Complete Workflow

```bash
git clone https://github.com/roomfulmoshe/Vertiport-Planner.git
cd Vertiport-Planner
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install jupyter notebook

mkdir -p taxi_zones nyc_tracts output

cd taxi_zones && curl -O https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip && unzip taxi_zones.zip && rm taxi_zones.zip && cd ..
cd nyc_tracts && curl -O https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/census-tracts/nyct2020_25c.zip && unzip nyct2020_25c.zip && mv nyct2020_25c/* . && rmdir nyct2020_25c && rm nyct2020_25c.zip && cd ..

python -c "import geopandas as gpd; gdf = gpd.read_file('nyc_tracts/nyct2020.shp'); gdf.to_file('nyc_tracts/nyc_tracts.json', driver='GeoJSON'); print('✓ GeoJSON created')"

python geospatial_join.py
python GenerateNeighborsCSVJSON.py
python LODES_2020_2022_OD_DEMAND.py
python ACS_demographics_tract_level.py

python -m http.server 8000
```

---

## Team & Attribution

**Team:**  
Moshe Shtaygrud, Nora A Fahim, Leonel A Castillo, Mohamed Rafee Kaza Kamaludeen, Emily G O'Connell, Allaa H Sharif

**Last Updated:** November 2025  
**Repository:** https://github.com/roomfulmoshe/Vertiport-Planner.git
