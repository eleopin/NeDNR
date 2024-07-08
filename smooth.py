import arcpy
import os
import time
import csv
from itertools import combinations

# Define workspace and settings
shpworkspace = r"C:\Users\eleopin\OneDrive - Stantec\Attachments\Desktop\NeDNR Python\test dataframes"
geodatabase = r"C:\Users\eleopin\OneDrive - Stantec\Documents\ArcGIS\Projects\NeDNR Python\NeDNR Python.gdb"
arcpy.env.workspace = shpworkspace
arcpy.env.overwriteOutput = True

# Spatial reference WKT for CSV conversion
wkt = """
GEOGCS['GCS_WGS_1984',DATUM['D_WGS_1984',SPHEROID['WGS_1984',6378137.0,298.257223563]],
PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]];
-400 -400 1000000000;-100000 10000;-100000 10000;8.98315284119522E-09;
0.001;0.001;IsHighPrecision
"""

# Start timer
start_time = time.time()

# List CSV files in the workspace
csvlist = arcpy.ListFiles("*.csv")

# Create spatial reference object
sr = arcpy.SpatialReference(text=wkt)

# Iterate over each CSV file
for csvfile in csvlist:
    outlayer = "CSVEventLayer"

    # Create feature class name for geodatabase
    fc_name = os.path.splitext(os.path.basename(csvfile))[0].replace('-', '_')
    output_fc = os.path.join(geodatabase, fc_name)

    # Make XY Event Layer and copy features to geodatabase
    arcpy.MakeXYEventLayer_management(csvfile, "long", "lat", outlayer, sr, "#")
    arcpy.CopyFeatures_management(outlayer, output_fc)

    print(f"CSV {csvfile} converted to shapefile in geodatabase as {fc_name}")

# List all feature classes in the geodatabase
arcpy.env.workspace = geodatabase
shplist = arcpy.ListFeatureClasses()

# Check for 'unit_classification' field once outside the loop
field_to_check = 'unit_classification'

# Loop through each feature class
for shpfile in shplist:
    # Print the filename of the feature class
    print("Processing feature class:", shpfile)

    # Use arcpy.ListFields to get a list of all fields in the feature class
    fields = arcpy.ListFields(shpfile)
    field_names = [field.name for field in fields]

    # Ensure 'unit_classification' field exists in the feature class
    if field_to_check in field_names:
        # Create a set to store unique values of 'unit_classification'
        unique_values = set()

        # Use a search cursor to find all distinct values of the "unit_classification" attribute
        with arcpy.da.SearchCursor(shpfile, ['unit_classification']) as cursor:
            for row in cursor:
                unique_values.add(row[0])

        # Iterate through each unique unit_classification value
        for value in unique_values:
            try:
                # Construct SQL query with proper delimiters and handling of string values
                if fields[0].type == 'String':
                    sql_query = "{} = '{}'".format(arcpy.AddFieldDelimiters(shpfile, 'unit_classification'), value)
                else:
                    sql_query = "{} = {}".format(arcpy.AddFieldDelimiters(shpfile, 'unit_classification'), value)

                # Create a feature class name for the output
                out_name = f"{os.path.splitext(os.path.basename(shpfile))[0]}_unit_class{value}"
                output_fc = os.path.join(geodatabase, out_name)

                # Use Select_analysis to create a new feature class for each unique value
                arcpy.Select_analysis(shpfile, output_fc, sql_query)

                print(f"  Split by unit_classification {value}: Saved as {out_name}")

                # Create Minimum Bounding Geometry (MBG) for the output feature class
                mbg_output_fc = f"{output_fc}_MBG"
                arcpy.MinimumBoundingGeometry_management(output_fc, mbg_output_fc, "CONVEX_HULL")

                print(f"  Created MBG for {out_name}: Saved as {mbg_output_fc}")


                arcpy.MakeFeatureLayer_management(output_fc, "points_layer")
                arcpy.MakeFeatureLayer_management(mbg_output_fc, "mbg_output_fc")
                arcpy.SelectLayerByLocation_management("points_layer", "WITHIN", "mbg_output_fc")
                count = int(arcpy.GetCount_management("points_layer")[0])

                print(f"  Minimum overlap points for {out_name}: {count}")

            except arcpy.ExecuteError as e:
                print(f"ExecuteError: {str(e)}")  # Print any specific error messages
            except Exception as e:
                print(f"Exception: {str(e)}")
    else:
        print(f"  Field '{field_to_check}' not found in {shpfile}. Skipping...")

#Function to get minimum overlapping points between two unit classes
def get_min_overlap_points(dataframe, unit_class1, unit_class2, geodatabase):
    points_file1 = f"dataframe_{dataframe}_unit_class{unit_class1}"
    points_file2 = f"dataframe_{dataframe}_unit_class{unit_class2}"
    envelope1 = f"dataframe_{dataframe}_unit_class{unit_class1}_MBG"
    envelope2 = f"dataframe_{dataframe}_unit_class{unit_class2}_MBG"

    arcpy.MakeFeatureLayer_management(points_file2, "points_layer1")
    arcpy.MakeFeatureLayer_management(envelope1, "envelope_layer1")
    arcpy.SelectLayerByLocation_management("points_layer1", "WITHIN", "envelope_layer1")
    count1 = int(arcpy.GetCount_management("points_layer1")[0])

    arcpy.MakeFeatureLayer_management(points_file1, "points_layer2")
    arcpy.MakeFeatureLayer_management(envelope2, "envelope_layer2")
    arcpy.SelectLayerByLocation_management("points_layer2", "WITHIN", "envelope_layer2")
    count2 = int(arcpy.GetCount_management("points_layer2")[0])

    return min(count1, count2)

dataframes = [str(i) for i in range(1, 51)]
unit_classes = ['1', '2', '3', '4', '5', '6']  

csv_output = r"C:\Users\eleopin\OneDrive - Stantec\Attachments\Desktop\NeDNR Python\overlap_counts_all_dataframes.csv"

with open(csv_output, 'w', newline='') as csvfile:
    csvwriter = csv.writer(csvfile)
    
    csvwriter.writerow(['Dataframe', 'Unit_Class1', 'Unit_Class2', 'Min_Overlap_Points', 'Sum_Min_Overlap'])
    
    for dataframe in dataframes:
        
        total_min_overlap = 0
       
        for unit_class1, unit_class2 in combinations(unit_classes, 2):

            min_overlap = get_min_overlap_points(dataframe, unit_class1, unit_class2, geodatabase)
            
            total_min_overlap += min_overlap

            csvwriter.writerow([dataframe, unit_class1, unit_class2, min_overlap])
        
        csvwriter.writerow([f"Total Sum for {dataframe}", '', '', '', total_min_overlap])

print(f"Overlap counts and total sums for all dataframes have been written to {csv_output}")

end_time = time.time()
execution_time = end_time - start_time
print(f"Script completed successfully. Total execution time: {execution_time:.2f} seconds")
