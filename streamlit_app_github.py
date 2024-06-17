# -*- coding: utf-8 -*-
"""
Created on Thu Jun 13 10:42:14 2024

@author: lmspi
"""

import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import cloudpickle
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point, MultiPolygon, Polygon
from shapely.ops import unary_union
import geopandas as gpd

def read_requirements(file_path):
    with open(file_path, 'r') as file:
        requirements = [line.strip() for line in file if line.strip()]
    return requirements

if __name__ == "__main__":
    # Read requirements.txt
    requirements_file = "requirements.txt"
    requirements = read_requirements(requirements_file)
    print("List of dependencies:")
    for requirement in requirements:
        print(requirement)

# Load data from pickles
with open('brt_score_sorted.pkl', 'rb') as f:
    new_df = cloudpickle.load(f)

with open('area_postcode4.pkl', 'rb') as f:
    area_postcode4 = cloudpickle.load(f)

# Ensure the 'population_center' column is available and is of type Point
if 'population_center' not in area_postcode4.columns or not all(isinstance(x, Point) for x in area_postcode4['population_center']):
    st.error("The 'population_center' column is not available or not of type Point in the data.")
else:
    # Set the coordinate reference system to the source CRS (EPSG:28992)
    area_postcode4 = gpd.GeoDataFrame(area_postcode4, geometry='population_center', crs='EPSG:28992')

    # Convert the coordinate system of the entire GeoDataFrame to WGS84 (EPSG:4326)
    area_postcode4 = area_postcode4.to_crs('EPSG:4326')

    # Convert the 'geometry' column (borders) to the same CRS
    area_postcode4['geometry'] = area_postcode4['geometry'].to_crs('EPSG:4326')

    # Streamlit app
    st.title('Postal Zone Pairs BRT Score Visualization')

    city_names = list(area_postcode4['postcode4'].unique())
    city_names.insert(0, "Overall")

    city_name = st.selectbox("Select a Postal Zone (or choose Overall for top 10 Postal zone pairs):", city_names)
    top_n = st.slider("Number of top postal zone pairs to display:", 1, 20, 10)

    # Filter data based on user selection
    if city_name != "Overall":
        filtered_df = new_df[(new_df['Origin'] == city_name) | (new_df['Destination'] == city_name)]
    else:
        filtered_df = new_df

    top_demand = filtered_df.nlargest(top_n, 'Demand')

    # Create map centered at the mean location of all population centers
    mean_lat = area_postcode4['population_center'].y.mean()
    mean_lon = area_postcode4['population_center'].x.mean()
    m = folium.Map(location=[mean_lat, mean_lon], zoom_start=10)

    marker_cluster = MarkerCluster().add_to(m)

    # Generate colors for the city pairs
    colors = plt.cm.tab10(np.linspace(0, 1, len(top_demand)))

    # Store city labels to prevent duplicates
    added_postal_codes = set()
    lines = []

    for i, row in enumerate(top_demand.itertuples(), start=1):
        filtered_origin = area_postcode4[area_postcode4['postcode4'] == row.Origin]
        if not filtered_origin.empty:
            origin = filtered_origin.iloc[0]

            filtered_destination = area_postcode4[area_postcode4['postcode4'] == row.Destination]
            if not filtered_destination.empty:
                destination = filtered_destination.iloc[0]

                # Add markers for origin and destination using population_center
                if row.Origin not in added_postal_codes:
                    folium.Marker(
                        location=[origin['population_center'].y, origin['population_center'].x],
                        popup=str(row.Origin),
                        icon=folium.Icon(color='blue')
                    ).add_to(marker_cluster)
                    added_postal_codes.add(row.Origin)

                if row.Destination not in added_postal_codes:
                    folium.Marker(
                        location=[destination['population_center'].y, destination['population_center'].x],
                        popup=str(row.Destination),
                        icon=folium.Icon(color='red')
                    ).add_to(marker_cluster)
                    added_postal_codes.add(row.Destination)

                color = f'#{int(colors[i % len(colors)][0]*255):02x}{int(colors[i % len(colors)][1]*255):02x}{int(colors[i % len(colors)][2]*255):02x}'

                # Add the polyline for the route using population_center
                polyline = folium.PolyLine(
                    locations=[[origin['population_center'].y, origin['population_center'].x], [destination['population_center'].y, destination['population_center'].x]],
                    color=color,
                    weight=5,
                    opacity=0.7
                ).add_to(m)
                lines.append((i, polyline))

                # Calculate the midpoint for the label
                midpoint = [(origin['population_center'].y + destination['population_center'].y) / 2, (origin['population_center'].x + destination['population_center'].x) / 2]

                # Add the ranking label at the midpoint
                folium.Marker(
                    location=midpoint,
                    icon=folium.DivIcon(
                        html=f"""
                        <div style="
                            background-color: white; 
                            border: 1px solid black; 
                            padding: 2px;
                            border-radius: 50%;
                            text-align: center;
                            font-size: 12px;
                            font-weight: bold;
                            width: 20px;
                            height: 20px;
                            line-height: 16px;  /* Adjusted line-height */
                            ">
                            {i}
                        </div>
                        """
                    )
                ).add_to(m)

    # Filter the polygons for the selected city or overall top pairs
    if city_name != "Overall":
        selected_polygons = area_postcode4[(area_postcode4['postcode4'] == city_name) | 
                                           (area_postcode4['postcode4'].isin(top_demand['Origin'])) |
                                           (area_postcode4['postcode4'].isin(top_demand['Destination']))]
    else:
        selected_polygons = area_postcode4[area_postcode4['postcode4'].isin(top_demand['Origin']) | 
                                           area_postcode4['postcode4'].isin(top_demand['Destination'])]

    # Ensure there are no missing geometries in selected_polygons
    selected_polygons = selected_polygons[~selected_polygons['geometry'].isnull()]

    # Check if selected_polygons is empty
    if selected_polygons.empty:
        st.error("No valid geometries found for the selected postal zones.")
    else:
        # Generate colors for the city borders
        city_colors = plt.cm.viridis(np.linspace(0, 1, len(selected_polygons)))

        # Add city borders with full lines
        for i, (_, row) in enumerate(selected_polygons.iterrows()):
            color = f'#{int(city_colors[i][0]*255):02x}{int(city_colors[i][1]*255):02x}{int(city_colors[i][2]*255):02x}'
            folium.GeoJson(
                row['geometry'],
                name=row['postcode4'],
                style_function=lambda feature, color=color: {
                    'fillColor': 'none',
                    'color': color,
                    'weight': 3,
                    'dashArray': ''
                }
            ).add_to(m)

        # Create overall study area border from all geometries in area_postcode4
        study_area = unary_union(area_postcode4['geometry'].tolist())

        # Extract the exterior for the entire study area
        if isinstance(study_area, MultiPolygon):
            study_area = unary_union([poly.convex_hull for poly in study_area.geoms])
        elif isinstance(study_area, Polygon):
            study_area = study_area.convex_hull

        folium.GeoJson(
            study_area,
            name='Study Area',
            style_function=lambda feature: {
                'fillColor': 'none',
                'color': 'black',
                'weight': 2,
                'dashArray': '5, 5'
            }
        ).add_to(m)

    folium_static(m)

    st.markdown("### Postal Zone Pairs with Highest BRT Score")

    # Create a copy of the DataFrame to avoid modifying the original one
    top_demand_copy = top_demand[['Origin', 'Destination', 'Demand']].copy()

    # Rename the 'Demand' column to 'BRT Score'
    top_demand_copy.rename(columns={'Demand': 'BRT Score'}, inplace=True)

    # Convert 'Origin' and 'Destination' to strings to avoid formatting with commas
    top_demand_copy['Origin'] = top_demand_copy['Origin'].astype(str)
    top_demand_copy['Destination'] = top_demand_copy['Destination'].astype(str)

    # Display the table with rounded and integer values, and index starting at 1
    df_display = top_demand_copy.round(0).astype(int).reset_index(drop=True).rename_axis('Ranking').reset_index()
    df_display['Ranking'] += 1
    df_display.set_index('Ranking', inplace=True)
    st.write(df_display)






