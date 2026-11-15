/**
 * Field Shift (NASA Space Apps Challenge 2026)
 * Google Earth Engine JavaScript API Pipeline
 * Study Area: Guelma Wilaya, Algeria
 * Dataset: COPERNICUS/S2_SR_HARMONIZED + COPERNICUS/S2_CLOUD_PROBABILITY
 * Period: 2016-12-01 (for Winter 2017 completeness check) to 2025-12-31
 *
 * Resolution policy:
 *  - NDVI (B8, B4) & EVI (B8, B4, B2): native 10 m (EPSG:32632)
 *  - NDMI (B8, B11) & NDRE (B8A, B5): native 20 m (EPSG:32632; B8 aggregated to 20 m)
 *  - Valid pixel coverage computed over Guelma boundary at native index resolution
 */

// Upload data/boundaries/processed/guelma_wilaya_boundary.geojson.gpkg to your active GEE project assets
// or adjust PROJECT_ASSET if stored under another shared asset path.
var PROJECT_ASSET = 'projects/spry-framework-514800-j2/assets/guelma_wilaya_boundary';
var guelmaFC = ee.FeatureCollection(PROJECT_ASSET);
var guelmaGeom = guelmaFC.geometry();

var TARGET_CRS = 'EPSG:32632';
var DRIVE_FOLDER = 'FieldShift_Sentinel2_Guelma';
var CLOUD_PROB_MAX = 40; // % threshold when S2_CLOUD_PROBABILITY match is available

// SCL classes to exclude:
// 0: No Data, 1: Saturated/defective, 3: Cloud shadows,
// 8: Cloud medium prob, 9: Cloud high prob, 10: Thin cirrus, 11: Snow/ice.
// Class 2 (Dark area pixels) is retained by default on Guelma relief to avoid
// removing valid shaded mountain vegetation / dark moist soils, and evaluated via QA.
var EXCLUDE_SCL = [0, 1, 3, 8, 9, 10, 11];

// 1. Load & inspect collections
var s2Raw = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(guelmaGeom)
  .filterDate('2016-12-01', '2026-01-01');

var s2CloudProb = ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
  .filterBounds(guelmaGeom)
  .filterDate('2016-12-01', '2026-01-01');

print('Total S2_SR_HARMONIZED images (2016-12 to 2025-12):', s2Raw.size());
print('Total S2_CLOUD_PROBABILITY images:', s2CloudProb.size());

// Join S2_SR_HARMONIZED with S2_CLOUD_PROBABILITY on system:index (left join)
var joinFilter = ee.Filter.equals({
  leftField: 'system:index',
  rightField: 'system:index'
});
var joined = ee.Join.saveFirst({
  matchKey: 'cloud_prob_img',
  outer: true
}).apply(s2Raw, s2CloudProb, joinFilter);

var s2Joined = ee.ImageCollection(joined);

// 2. Cloud/shadow masking & index computation (preserving reflectance scale 1/10000)
function maskAndComputeIndices(img) {
  img = ee.Image(img);
  var scl = img.select('SCL');

  // Build SCL valid mask
  var validScl = ee.Image(1);
  EXCLUDE_SCL.forEach(function(cls) {
    validScl = validScl.and(scl.neq(cls));
  });

  // Optional S2_CLOUD_PROBABILITY mask when matched
  var cpObj = img.get('cloud_prob_img');
  var validCp = ee.Image(ee.Algorithms.If(
    cpObj,
    ee.Image(cpObj).select('probability').lt(CLOUD_PROB_MAX),
    ee.Image(1)
  ));

  var mask = validScl.and(validCp);

  var blue = img.select('B2').multiply(0.0001);
  var green = img.select('B3').multiply(0.0001);
  var red = img.select('B4').multiply(0.0001);
  var re1 = img.select('B5').multiply(0.0001);
  var nir = img.select('B8').multiply(0.0001);
  var nirNarrow = img.select('B8A').multiply(0.0001);
  var swir1 = img.select('B11').multiply(0.0001);

  var ndvi = nir.subtract(red).divide(nir.add(red)).rename('NDVI');
  var eviDenom = nir.add(red.multiply(6.0)).subtract(blue.multiply(7.5)).add(1.0);
  var evi = nir.subtract(red).multiply(2.5).divide(eviDenom.where(eviDenom.eq(0), 1e-6)).rename('EVI');
  var ndmi = nir.subtract(swir1).divide(nir.add(swir1)).rename('NDMI');
  var ndre = nirNarrow.subtract(re1).divide(nirNarrow.add(re1)).rename('NDRE');

  return img.select(['B2', 'B3', 'B4', 'B8']).multiply(0.0001)
    .addBands([ndvi, evi, ndmi, ndre])
    .updateMask(mask)
    .copyProperties(img, ['system:time_start', 'CLOUDY_PIXEL_PERCENTAGE']);
}

var s2Prepared = s2Joined.map(maskAndComputeIndices);

// Study-area reference masks for pixel counts at 10m and 20m
var ones10m = ee.Image.constant(1).clip(guelmaGeom).rename('total_px');
var totalPx10m = ee.Number(ones10m.reduceRegion({
  reducer: ee.Reducer.count(),
  geometry: guelmaGeom,
  scale: 10,
  crs: TARGET_CRS,
  maxPixels: 1e10
}).get('total_px'));

var totalPx20m = ee.Number(ones10m.reduceRegion({
  reducer: ee.Reducer.count(),
  geometry: guelmaGeom,
  scale: 20,
  crs: TARGET_CRS,
  maxPixels: 1e10
}).get('total_px'));

// Helper: summarize a composite at 10m (NDVI, EVI) and 20m (NDMI, NDRE)
function summarizeComposite(col, labelProps) {
  var imgCount = col.size();
  var composite = ee.Image(ee.Algorithms.If(
    imgCount.gt(0),
    col.select(['NDVI', 'EVI', 'NDMI', 'NDRE']).median().clip(guelmaGeom),
    ee.Image.constant([0, 0, 0, 0]).rename(['NDVI', 'EVI', 'NDMI', 'NDRE']).updateMask(ee.Image(0))
  ));
  var validObs10 = ee.Image(ee.Algorithms.If(
    imgCount.gt(0),
    col.select('NDVI').count().clip(guelmaGeom),
    ee.Image.constant(0).updateMask(ee.Image(0))
  ));
  var validObs20 = ee.Image(ee.Algorithms.If(
    imgCount.gt(0),
    col.select('NDMI').count().clip(guelmaGeom),
    ee.Image.constant(0).updateMask(ee.Image(0))
  ));

  var reducer = ee.Reducer.median()
    .combine(ee.Reducer.mean(), '', true)
    .combine(ee.Reducer.stdDev(), '', true)
    .combine(ee.Reducer.count(), '', true);

  var stats10 = composite.select(['NDVI', 'EVI']).reduceRegion({
    reducer: reducer,
    geometry: guelmaGeom,
    scale: 10,
    crs: TARGET_CRS,
    maxPixels: 1e10,
    tileScale: 4
  });

  var stats20 = composite.select(['NDMI', 'NDRE']).reduceRegion({
    reducer: reducer,
    geometry: guelmaGeom,
    scale: 20,
    crs: TARGET_CRS,
    maxPixels: 1e10,
    tileScale: 4
  });

  var obs10Mean = validObs10.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: guelmaGeom,
    scale: 10,
    crs: TARGET_CRS,
    maxPixels: 1e10,
    tileScale: 4
  });
  var obs20Mean = validObs20.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: guelmaGeom,
    scale: 20,
    crs: TARGET_CRS,
    maxPixels: 1e10,
    tileScale: 4
  });

  var props = ee.Dictionary(labelProps)
    .set('image_count', imgCount)
    .set('total_pixels_10m', totalPx10m)
    .set('total_pixels_20m', totalPx20m)
    .set('mean_valid_obs_per_px_10m', obs10Mean.get('NDVI'))
    .set('mean_valid_obs_per_px_20m', obs20Mean.get('NDMI'))
    .combine(stats10)
    .combine(stats20);

  return ee.Feature(null, props);
}

// 3. Monthly summaries (108 months: 2017-01 .. 2025-12)
var monthlyFeatures = [];
for (var y = 2017; y <= 2025; y++) {
  for (var m = 1; m <= 12; m++) {
    var start = ee.Date.fromYMD(y, m, 1);
    var end = start.advance(1, 'month');
    var sub = s2Prepared.filterDate(start, end);
    monthlyFeatures.push(summarizeComposite(sub, {
      year: y,
      month: m,
      start_date: start.format('YYYY-MM-dd'),
      end_date: end.advance(-1, 'day').format('YYYY-MM-dd')
    }));
  }
}

Export.table.toDrive({
  collection: ee.FeatureCollection(monthlyFeatures),
  description: 'sentinel2_monthly_indices_2017_2025',
  folder: DRIVE_FOLDER,
  fileNamePrefix: 'sentinel2_monthly_indices_2017_2025',
  fileFormat: 'CSV'
});

// 4. Seasonal summaries + selected seasonal GeoTIFFs
var seasons = [
  {name: 'Winter', offsetYear: -1, startMonth: 12, endYearOffset: 0, endMonth: 3},
  {name: 'Spring', offsetYear: 0, startMonth: 3, endYearOffset: 0, endMonth: 6},
  {name: 'Summer', offsetYear: 0, startMonth: 6, endYearOffset: 0, endMonth: 9},
  {name: 'Autumn', offsetYear: 0, startMonth: 9, endYearOffset: 0, endMonth: 12}
];

var seasonalFeatures = [];
for (var sy = 2017; sy <= 2025; sy++) {
  seasons.forEach(function(s) {
    var start = ee.Date.fromYMD(sy + s.offsetYear, s.startMonth, 1);
    var end = ee.Date.fromYMD(sy + s.endYearOffset, s.endMonth, 1);
    var sub = s2Prepared.filterDate(start, end);
    seasonalFeatures.push(summarizeComposite(sub, {
      season_year: sy,
      season: s.name,
      start_date: start.format('YYYY-MM-dd'),
      end_date: end.advance(-1, 'day').format('YYYY-MM-dd')
    }));
  });
}

Export.table.toDrive({
  collection: ee.FeatureCollection(seasonalFeatures),
  description: 'sentinel2_seasonal_indices_2017_2025',
  folder: DRIVE_FOLDER,
  fileNamePrefix: 'sentinel2_seasonal_indices_2017_2025',
  fileFormat: 'CSV'
});

// 5. Annual summaries + 2017 & 2025 GeoTIFF exports
var annualFeatures = [];
for (var ay = 2017; ay <= 2025; ay++) {
  var aStart = ee.Date.fromYMD(ay, 1, 1);
  var aEnd = ee.Date.fromYMD(ay + 1, 1, 1);
  var aSub = s2Prepared.filterDate(aStart, aEnd);
  annualFeatures.push(summarizeComposite(aSub, {
    year: ay,
    start_date: aStart.format('YYYY-MM-dd'),
    end_date: aEnd.advance(-1, 'day').format('YYYY-MM-dd')
  }));

  if (ay === 2017 || ay === 2025) {
    var comp10 = aSub.select(['B4', 'B3', 'B2', 'B8', 'NDVI', 'EVI']).median().clip(guelmaGeom).toFloat();
    Export.image.toDrive({
      image: comp10,
      description: 'sentinel2_annual_' + ay + '_10m',
      folder: DRIVE_FOLDER,
      fileNamePrefix: 'sentinel2_annual_' + ay + '_10m',
      region: guelmaGeom,
      scale: 10,
      crs: TARGET_CRS,
      maxPixels: 1e10
    });

    var comp20 = aSub.select(['NDMI', 'NDRE']).median().clip(guelmaGeom).toFloat();
    Export.image.toDrive({
      image: comp20,
      description: 'sentinel2_annual_' + ay + '_20m',
      folder: DRIVE_FOLDER,
      fileNamePrefix: 'sentinel2_annual_' + ay + '_20m',
      region: guelmaGeom,
      scale: 20,
      crs: TARGET_CRS,
      maxPixels: 1e10
    });
  }
}

Export.table.toDrive({
  collection: ee.FeatureCollection(annualFeatures),
  description: 'sentinel2_annual_indices_2017_2025',
  folder: DRIVE_FOLDER,
  fileNamePrefix: 'sentinel2_annual_indices_2017_2025',
  fileFormat: 'CSV'
});

// 6. Multi-year seasonal composites (2018-2025 complete seasons) & coverage raster
seasons.forEach(function(s) {
  var seasonCol = ee.ImageCollection([]);
  for (var sy = 2018; sy <= 2025; sy++) {
    var st = ee.Date.fromYMD(sy + s.offsetYear, s.startMonth, 1);
    var en = ee.Date.fromYMD(sy + s.endYearOffset, s.endMonth, 1);
    seasonCol = seasonCol.merge(s2Prepared.filterDate(st, en));
  }
  Export.image.toDrive({
    image: seasonCol.select(['NDVI', 'EVI']).median().clip(guelmaGeom).toFloat(),
    description: 'sentinel2_seasonal_' + s.name.toLowerCase() + '_10m',
    folder: DRIVE_FOLDER,
    fileNamePrefix: 'sentinel2_seasonal_' + s.name.toLowerCase() + '_10m',
    region: guelmaGeom,
    scale: 10,
    crs: TARGET_CRS,
    maxPixels: 1e10
  });
  Export.image.toDrive({
    image: seasonCol.select(['NDMI', 'NDRE']).median().clip(guelmaGeom).toFloat(),
    description: 'sentinel2_seasonal_' + s.name.toLowerCase() + '_20m',
    folder: DRIVE_FOLDER,
    fileNamePrefix: 'sentinel2_seasonal_' + s.name.toLowerCase() + '_20m',
    region: guelmaGeom,
    scale: 20,
    crs: TARGET_CRS,
    maxPixels: 1e10
  });
});

// Valid observation count map over 2017-2025 (20m common analysis grid)
var validCount20m = s2Prepared.filterDate('2017-01-01', '2026-01-01')
  .select('NDVI').count().clip(guelmaGeom).toInt32();
Export.image.toDrive({
  image: validCount20m,
  description: 'sentinel2_valid_obs_count_2017_2025_20m',
  folder: DRIVE_FOLDER,
  fileNamePrefix: 'sentinel2_valid_obs_count_2017_2025_20m',
  region: guelmaGeom,
  scale: 20,
  crs: TARGET_CRS,
  maxPixels: 1e10
});
