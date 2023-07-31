# BII-Land-Use-and-Intensity-for-Sub-Saharan-Africa
BII: Land Use and Intensity for Sub-Saharan Africa

## BII project land use and intensity
This code folder contains the code for extracting, pre-processing, applying an expert defined decision tree and computing the intensity values of six categories of land use at a 1x1 and 8x8 km spatial resolution for a single country or the entire afrotropic region. 

Refer to NB1_1km_country to run the above mentioned analysis for a single country at an 1km spatial resolution.  
Refer to NB2_1km_Afrotropic to run the same analysis for the entire afrotropic region.  
Refer to NB1_8km_country to run the same analysis for a single country at an 8km spatial resolution.  
Refer to NB2_8km_Afrotropic to run the same analysis for the entire afrotropic region at an 8km spatial resolution.

The Data extraction for all countries need to be executed before proceeding to the afrotropic notebooks. The notebook titled "NB1_8km_country.ipynb" provides two methods for extracting data. A more automated approach based on the extractData.py module to automatically extract data for all afrotropic countries. Alternatively, the user can download the data for a single country at a time using the available option 1 (provided in both "NB1_8km_country.ipynb" and "NB1_1km_country.ipynb")

### High-level steps
1. sub saharan african countries are identified (filtered)
2. A grid is created for the country of interest
3. All variables (Refer to list of variables.docx) required are extracted from Google Earth Engine at the aggregated 1km scale
4. Datasets are combined and pre-processed. Includes, filling in missing data, scaling data and correcting data types.
5. The expert decision tree is applied that outputs a land use for every point
6. Data is scaled and the intensity scores are computed
