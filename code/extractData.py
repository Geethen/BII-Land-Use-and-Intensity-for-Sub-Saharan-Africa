# Setup parameters
import ee
from datetime import datetime
import geemap
from geeml.utils import createGrid
from geeml.extract import extractor

import os

class bii:

    def __init__(self, country: str, mode: str, outPath: str, proj, aoiMode:str = 'grid', plot: bool = False):
        """Initialize the class with the country and mode of analysis
        
        Args:
            country (str): Name of the country to extract data for. Must be in the list of countries in the config file.
            mode (str): '8km or '1km' resolution to extract data
            outPath (str): Path to save data
            proj (str): Projection of the data
            aoiMode (str): 'country' or 'grid'. Default 'grid'. Use country boundary or the gridcells
            that intersect with the country boundary. To avoid boundary effects use 'grid'. 
            plot (bool): Plot the country boundary. Default False.
            
        Returns:
            None
            """
        self.country = country
        self.mode = mode
        self.aoiMode = aoiMode
        self.outPath = outPath
        self.proj = proj
        self.wkt = self.proj.wkt().getInfo()

        self.createConfig()

        # Get current date- used for saving files
        self.date = datetime.today().strftime('%d%m%Y')

        self.aoi = self.config.get(self.country).get('aoi').geometry()

        # Set path for saving data
        dd = self.config.get(self.country).get('dd')
        if not os.path.exists(dd):
            os.makedirs(dd)
            os.chdir(dd)
            print(f"Created and set directory to: {os.getcwd()}")
        else:
            os.chdir(dd)
            print(f"Directory already exists. Set directory to: {os.getcwd()}")

        if plot:
            self._plotCountry()

    def createConfig(self):
        """Create a dictionary of country names and their corresponding aoi and save path
        
        Returns:
            config (dict): Dictionary of country names and their corresponding aoi and save path"""
        
        countries = ee.FeatureCollection("USDOS/LSIB/2017")
        c2 = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
        afroTropics = ee.FeatureCollection("projects/ee-geethensingh/assets/Afrotropics")

        africa = c2.filter(ee.Filter.eq('wld_rgn', 'Africa'))
        sub = countries.filterBounds(afroTropics).aggregate_array('COUNTRY_NA')\
        .removeAll(['Gaza Strip (disp)','Israel', 'Algeria', 'Egypt', 'Libya', 'Morocco', 'Tunisia', 'Mayotte (Fr)',
                    'Spain [Canary Is]', 'Spain [Plazas de Soberania]', 'Portugal [Madeira Is]'])

        sub_africa = countries.filter(ee.Filter.inList('COUNTRY_NA', sub))

        country_list = sub_africa.aggregate_array('COUNTRY_NA').getInfo()

        config = {}
        for country in country_list:
            csavepath = f"{self.outPath}/{country}"
            caoi = sub_africa.filter(ee.Filter.eq('COUNTRY_NA', country))
            config[country] = {'dd':csavepath,
                            'aoi':caoi}
        self.config = config
    
    def _plotCountry(self):
        Map = geemap.Map()
        Map.centerObject(self.aoi, 3)
        Map.addLayer(self.aoi)
        Map

    
    def extractData(self, sumCovariates: bool = True, coords: bool = True, meanCovariates: bool = True, fieldSize: bool = False, batchSize: int = 5000):
        if self.mode == '8km':
            print("Creating 8km grid")
            grid, _ = createGrid(8000, ee.Feature(self.aoi), crs = self.proj)
        else:
            print("Creating 1km grid")
            grid, _ = createGrid(1000, ee.Feature(self.aoi), crs = self.proj)

        if (self.mode == '8km') & (self.aoiMode == 'grid'):
            self.aoi = grid.union(500).geometry()
        elif (self.mode == '1km') & (self.aoiMode == 'grid'):
            areaBuffer = self.aoi.buffer(1500, 1000)

        dd = self.config.get(self.country).get('dd')

        area = ee.Image.pixelArea().divide(1e6).clip(areaBuffer)
        urban_cover = ee.ImageCollection("projects/sat-io/open-datasets/WSF/WSF_2019").filterBounds(self.aoi)\
        .mosaic().eq(255).unmask(0)
        urbanAreaImage = area.multiply(urban_cover).rename('areakm2_urban')

        # Crop cover (30 m)
        crop_cover = ee.ImageCollection("users/potapovpeter/Global_cropland_2019").filterBounds(self.aoi).mosaic()
        cropAreaImage = area.multiply(crop_cover).rename('areakm2_cropCover')

        # Protected area old asset-projects/ee-geethensingh/assets/WDPA_Africa_strict
        prot_areas = ee.FeatureCollection("projects/ee-geethensingh/assets/WDPA_strict_032023").filterBounds(self.aoi)
        protectedAreaImage = area.clipToCollection(prot_areas).unmask(0).rename('areakm2_protArea')    

        # Plantation and tree crop
        result = ee.ImageCollection("users/liuzhujun/SDPT_NEW").mosaic()
        plantag = ee.Image("users/duzhenrong/SDPT/sdpt_plantag")
        china_plantyear = ee.ImageCollection("users/liuzhujun/SDPT_China").mosaic().rename('plantyear')
        DescalesOP = ee.ImageCollection("users/liuzhujun/Descales").mosaic()
        op = DescalesOP.updateMask(DescalesOP.gt(1980)).rename('plantyear')
        sdpt_name = ee.Image("users/duzhenrong/SDPT/sdpt_name")

        china_plantyear=china_plantyear.updateMask(china_plantyear.gt(1980))
        result=result.rename('plantyear').updateMask((sdpt_name.lt(120).And(sdpt_name.gt(0))).Or(sdpt_name.gt(129))).toInt32()

        plantationForest=ee.ImageCollection([result.updateMask(plantag.eq(1)),china_plantyear]).mosaic().gt(0).unmask(0) 
        plantationAreaImage = area.updateMask(plantationForest).rename('areakm2_plantation')
        treeCrop=result.multiply(plantag.eq(2))
        treeCrop =ee.ImageCollection([treeCrop,op]).mosaic().gt(0)  
        treeCropAreaImage = area.multiply(treeCrop).rename('areakm2_treeCrop')

        #Soil nutrients
        Soil_Lownutrient = ee.FeatureCollection("projects/ee-geethensingh/assets/Bell_1982_nutrient_map")\
        .filter(ee.Filter.eq('Nut_status', 'Low'))
        Soil_Mednutrient = ee.FeatureCollection("projects/ee-geethensingh/assets/Bell_1982_nutrient_map")\
        .filter(ee.Filter.eq('Nut_status', 'Medium'))
        Soil_Highnutrient = ee.FeatureCollection("projects/ee-geethensingh/assets/Bell_1982_nutrient_map")\
        .filter(ee.Filter.eq('Nut_status', 'High'))

        soilLowNutrientAreaImage = area.clipToCollection(Soil_Lownutrient).unmask(0).rename('areakm2_slowNutrArea')
        soilMedNutrientAreaImage = area.clipToCollection(Soil_Mednutrient).unmask(0).rename('areakm2_sMedNutriArea')
        soilHighNutrientAreaImage = area.clipToCollection(Soil_Highnutrient).unmask(0).rename('areakm2_sHighNutriArea')

        # Population Density
        popDensity = ee.ImageCollection("CIESIN/GPWv411/GPW_UNWPP-Adjusted_Population_Density")\
        .select('unwpp-adjusted_population_density').filterBounds(self.aoi).mosaic().rename('popDensity').unmask(0)
                                            
        # Grazing Intensity
        area = ee.Image('projects/ee-geethensingh/assets/GrazingDensity/GI_8_Areakm').unmask(0)
        cattleDensity = ee.Image('projects/ee-geethensingh/assets/GrazingDensity/5_Ct_2010_Da').divide(area).rename('cattleDensity').unmask(0)
        sheepDensity = ee.Image('projects/ee-geethensingh/assets/GrazingDensity/5_Sh_2010_Da').divide(area).rename('sheepDensity').unmask(0)
        goatDensity = ee.Image('projects/ee-geethensingh/assets/GrazingDensity/5_Gt_2010_Da').divide(area).rename('goatDensity').unmask(0)

        # Precipitation
        years = list(range(1991,2021))
        precipitation = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(self.aoi)  
        precipitation = ee.Image(ee.ImageCollection(ee.List(years).map(lambda year: precipitation\
        .filterDate(ee.Number(year).format(), ee.Number(year).add(1).format()).sum())).mean().rename('mm_precipitation')).unmask(0)

        # Nitrogen input
        proj = ee.Projection('EPSG:4326').scale(0.25,0.25)
        gridN = self.aoi.coveringGrid(proj)

        nInput = ee.FeatureCollection("projects/ee-geethensingh/assets/Nfur_15arcmins_transformed").filterBounds(self.aoi)\
        .map(lambda x: x.set("Nfer_type",ee.Algorithms.ObjectType(x.get("Nfer_kgha_"))))
        nInputStr = nInput.filter(ee.Filter.eq('Nfer_type', 'String')).map(lambda x: x.set("Nfer_kgha_",ee.Number.parse(x.get("Nfer_kgha_")).toFloat()))
        nInputNumber = nInput.filter(ee.Filter.neq('Nfer_type', 'String')).map(lambda x: x.set("Nfer_kgha_",ee.Number(x.get("Nfer_kgha_")).toFloat()))

        nInput = nInputStr.merge(nInputNumber)

        def pointToGrid(ft):
            feat = ee.Feature(ft)
            first = nInput.filterBounds(feat.geometry()).aggregate_first('Nfer_kgha_')
            return feat.set('Nfer_kgha_', first)

        nInput = gridN.filterBounds(nInput).map(pointToGrid)\
        .reduceToImage(**{'properties': ee.List(["Nfer_kgha_"]), 'reducer': ee.Reducer.first()})\
        .rename('Nfer_kgha').unmask(0)

        # FieldSize
        nfieldpts = ee.FeatureCollection("projects/ee-geethensingh/assets/dominant_field_sizes").filterBounds(self.aoi).size().getInfo()
        print(f"There are {nfieldpts} field points")
        if (fieldSize==True) & (nfieldpts>0):
            fieldSize = geemap.ee_to_geopandas(ee.FeatureCollection("projects/ee-geethensingh/assets/dominant_field_sizes")\
                                        .filterBounds(self.aoi)\
                                        .filter(ee.Filter.neq('field_size', 'NA'))\
                                        .map(lambda x: x.set("fieldSize",ee.Number.parse(x.get("field_size")))\
                                        ).select(['fieldSize', 'geometry'])).set_crs('EPSG:4326').to_crs(self.wkt)
        print("Extracting data")
        # # Extract data
        if sumCovariates:
            sumCovariates = urbanAreaImage.addBands([cropAreaImage, protectedAreaImage, soilLowNutrientAreaImage,\
                                                soilMedNutrientAreaImage, soilHighNutrientAreaImage,\
                                                plantationAreaImage, treeCropAreaImage])

            # extract 30m datasets for 8km grid using sum reducer
            extractor(sumCovariates, self.aoi, scale = 30, dd = dd, target = grid, crs = self.proj, num_threads = 25)\
            .extractByGrid(reduce = True, reducer = ee.Reducer.sum(), gridSize = 100000, batchSize = batchSize, filename = f"sum_{self.mode}.csv")

        if coords:
            coords = ee.Image.pixelCoordinates(self.proj)

            # extract coords at 8km scale using first reducer
            extractor(coords, self.aoi, scale = 1000, dd = dd, target = grid, crs = self.proj, num_threads = 25)\
            .extractByGrid(reduce = True, reducer = ee.Reducer.first(), gridSize = 100000, batchSize = batchSize, filename = f"coords_{self.mode}.csv")

        if meanCovariates:
            # Extract precipitation, nitrogen Input and density variables
            meanCovariates = precipitation.addBands([nInput, popDensity,\
                                                    sheepDensity, goatDensity,cattleDensity])

            extractor(meanCovariates, self.aoi, scale = 1000, dd = dd, target = grid, crs = self.proj, num_threads = 25)\
            .extractByGrid(reduce = True, reducer = ee.Reducer.mean(), gridSize = 100000, batchSize = batchSize, filename = f"mean_{self.mode}.csv")


# Run checks
# Compute Land Use
# Compute intensity
# Convert to raster