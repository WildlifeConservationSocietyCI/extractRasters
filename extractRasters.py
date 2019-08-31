# extractRasters.py
# Saves out individual rasters masked by records in a polygon layer from underlying raster
# 0.1 kf: basic functionality
# 0.2 kf: upgraded to 9.3 / Python 2.5; using new 9.3 SnapRaster property
# 0.3 kf: simplified and moved inputs into toolbox model; using in_memory for intermediate feature class
# 0.4 kf: proper use of scratch workspace; some optimization
# 0.5 kf: fixed crashing by deleting scratch files from ScratchWorkspace when done; added Background null value parameter to SaveRaster
#
# Note: when saving to jpg, the 0-value pixels in the "corners" will contain jpeg noise
# Note: we deliberately override statistics and pyramids settings in raster storage environment, so setting those in the GUI will have no effect

# TODO: Parallel Python


# Setup
import arcgisscripting, utilities as util
gp = arcgisscripting.create(9.3)
gp.overWriteOutput = 1
dirScratch = util.returnScratchWorkSpace(gp)
gp.AddMessage("Scratch directory: " + dirScratch)
gp.pyramid = "NONE"
gp.rasterStatistics = "NONE"
gp.AddMessage("pyramid: " + gp.pyramid)
gp.AddMessage("rasterStatistics: " + gp.rasterStatistics)

# Inputs
inFeatures = gp.GetParameterAsText(0)
idField = gp.GetParameterAsText(1)
inRaster = gp.GetParameterAsText(2)
dirOutput = gp.GetParameterAsText(3) + "/"
outputFormat = gp.GetParameterAsText(4)
if outputFormat == "GRID": outputFormat = ""

try:
    gp.AddMessage("Checking out Spatial Analyst license")
    if gp.CheckExtension("spatial") == "Available":
        gp.CheckOutExtension("spatial")
    else:
        raise "LicenseError"

    # Get extent of input features for resetting on each loop
    inFeaturesDesc = gp.Describe(inFeatures)
    gp.Extent = inFeaturesDesc.Extent
    
    # Everything should snap to the input raster -- SnapRaster is new to 9.3
    gp.SnapRaster = inRaster
    # Get cellsize from input raster
    try: # if it is a single-band image
        inRasterDesc = gp.Describe(inRaster)
        cellSize = float(inRasterDesc.MeanCellHeight)
    except: # if it is a multiband image, use Band_1
        inRasterDesc = gp.Describe(inRaster + "/Band_1")
        cellSize = float(inRasterDesc.MeanCellHeight)
    
    # loop over features
    rows = gp.SearchCursor(inFeatures)
    rows.Reset()
    row = rows.Next()

    gp.AddMessage("Starting loop...")
    while row:
        rid = str(row.GetValue(idField))
        extractedFeature = "in_memory/extract" + rid
        rasterMask = dirScratch + "mask" + rid
        
        # save out single record as temporary shapefile
        gp.Extent = inFeaturesDesc.Extent # reset extent
        gp.Select_analysis(inFeatures, extractedFeature, ' "' + idField + '" = ' + rid + ' ')

        # set extent in environment settings to extent of feature, with original raster as snap raster
        gp.Extent = gp.Describe(extractedFeature).Extent

        # create a mask from the single-record shp
        gp.PolygonToRaster_conversion(extractedFeature, idField, rasterMask, "CELL_CENTER", "", cellSize)

        #extract by (raster) mask
        try:
            gp.AddMessage("Extracting to " + dirOutput + rid + outputFormat)
            gp.ExtractByMask_sa(inRaster, rasterMask, dirScratch + rid) # "r": GRIDs can't begin with numbers
            # For some reason ExtractByMask sometimes converts to 16-bit. We have to convert back to 8-bit.
            # Looks like we can do output format conversion at the same time.
            gp.CopyRaster_management(dirScratch + rid, dirOutput + rid + outputFormat, "", 0, "", "", "", "8_BIT_UNSIGNED")

        except:
            gp.AddMessage("Tripped row exception: " + rid)
            gp.GetMessages()
        
        row = rows.Next()
        
        # Cleanup -- if dirScratch is the default Windows temp dir (or maybe even if not) and it gets too full, everything will crash
        gp.delete(extractedFeature)
        gp.delete(rasterMask)
        gp.delete(dirScratch + rid)
        
    gp.CheckInExtension("Spatial")

except "LicenseError":
    gp.AddMessage("Spatial Analyst license is unavailable")
    
except:
    gp.GetMessages()
