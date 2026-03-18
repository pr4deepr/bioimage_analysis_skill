# Image I/O Cookbook

Complete, runnable code patterns for reading and writing microscopy images in Python.

## Reading Images

### TIFF with tifffile

**Input**: path to a `.tif` or `.tiff` file (single-channel or multi-channel).
**Output**: NumPy array with shape `(Y, X)` for 2D or `(Z, Y, X)` / `(C, Y, X)` for stacks.

```python
import tifffile
import numpy as np

# Read the entire TIFF file into a NumPy array
image = tifffile.imread("path/to/image.tif")

# Inspect the shape and data type — important for choosing downstream processing
print(f"Shape: {image.shape}")   # e.g. (512, 512) for 2D, (30, 512, 512) for a Z-stack
print(f"Dtype: {image.dtype}")   # e.g. uint16 for 16-bit microscopy images
print(f"Min: {image.min()}, Max: {image.max()}")  # sanity check intensity range
```

### TIFF with skimage.io

**Input**: path to a `.tif` file.
**Output**: NumPy array, same as above.

```python
from skimage.io import imread

# skimage.io.imread wraps tifffile for TIFFs and uses other plugins for PNG, JPEG, etc.
image = imread("path/to/image.tif")

# For multi-page TIFFs (Z-stacks), skimage reads all pages automatically
print(f"Shape: {image.shape}")
print(f"Dtype: {image.dtype}")
```

### Proprietary formats with BioIO (CZI, LIF, ND2, OME-TIFF)

**Input**: path to a proprietary microscopy file (`.czi`, `.lif`, `.nd2`, `.ome.tif`, etc.).
**Output**: NumPy array with dimension order specified by BioIO (typically `TCZYX`).

```python
from bioio import BioImage

# Open the file — BioIO auto-detects the format
# For specific formats, install the matching reader:
#   pip install bioio-czi    (for Zeiss .czi)
#   pip install bioio-lif    (for Leica .lif)
#   pip install bioio-nd2    (for Nikon .nd2)
#   pip install bioio-ome-tiff  (for OME-TIFF)
bio_image = BioImage("path/to/image.czi")

# Show the dimension order and shape
print(f"Dims: {bio_image.dims}")           # e.g. <Dimensions [T: 1, C: 3, Z: 30, Y: 512, X: 512]>
print(f"Shape: {bio_image.shape}")         # e.g. (1, 3, 30, 512, 512)
print(f"Channel names: {bio_image.channel_names}")  # e.g. ['DAPI', 'GFP', 'mCherry']

# Get the full 5D array (T, C, Z, Y, X)
full_data = bio_image.data  # shape: (T, C, Z, Y, X)

# --- Extract individual channels from multi-channel data ---

# Option A: slice the full array (C is axis 1 in TCZYX)
dapi_channel = full_data[0, 0, :, :, :]      # first timepoint, first channel, all Z/Y/X
gfp_channel = full_data[0, 1, :, :, :]       # first timepoint, second channel

# Option B: use BioIO's get_image_data for named dimension slicing
# "ZYX" means: return a 3D array with only Z, Y, X dimensions
dapi_channel = bio_image.get_image_data("ZYX", T=0, C=0)
gfp_channel = bio_image.get_image_data("ZYX", T=0, C=1)

# For a 2D max-projection of one channel (common starting point for segmentation)
dapi_max_proj = dapi_channel.max(axis=0)  # collapse Z by taking max intensity
print(f"Max projection shape: {dapi_max_proj.shape}")  # (Y, X)
```

### Metadata extraction (pixel size, channels, dimensions)

Pixel size (physical scale) is critical for converting measurements from pixels to micrometers.

#### From BioIO (recommended for proprietary formats)

```python
from bioio import BioImage

bio_image = BioImage("path/to/image.czi")

# Physical pixel sizes in micrometers
pixel_size_um = bio_image.physical_pixel_sizes
print(f"Z spacing:  {pixel_size_um.Z} µm")   # e.g. 0.5
print(f"Y pixel:    {pixel_size_um.Y} µm")    # e.g. 0.065
print(f"X pixel:    {pixel_size_um.X} µm")    # e.g. 0.065

# Channel names (useful for labeling plots and output columns)
print(f"Channels: {bio_image.channel_names}")  # e.g. ['DAPI', 'GFP', 'mCherry']

# Full dimension info
print(f"Dimensions: {bio_image.dims}")
```

#### From TIFF tags (when you only have a plain TIFF)

```python
import tifffile

# Open the TIFF and read metadata from the first page's tags
with tifffile.TiffFile("path/to/image.tif") as tif:
    page = tif.pages[0]

    # Resolution tags store pixels-per-unit; we need to invert for unit-per-pixel
    x_res = page.tags.get("XResolution")
    y_res = page.tags.get("YResolution")

    if x_res is not None:
        # XResolution is stored as a fraction (numerator, denominator)
        numerator, denominator = x_res.value
        pixels_per_um = numerator / denominator
        pixel_size_x_um = 1.0 / pixels_per_um
        print(f"Pixel size X: {pixel_size_x_um} µm")
    else:
        print("No XResolution tag found — pixel size unknown")

    # ImageJ-style TIFFs store metadata in the ImageDescription tag
    description = page.tags.get("ImageDescription")
    if description is not None:
        print(f"ImageDescription:\n{description.value}")
        # Look for lines like "spacing=0.5" (Z spacing) or "unit=um"

    # For ImageJ metadata specifically:
    if tif.imagej_metadata is not None:
        ij_meta = tif.imagej_metadata
        print(f"ImageJ metadata keys: {list(ij_meta.keys())}")
        # Common keys: 'spacing' (Z step), 'unit', 'channels', 'slices', 'frames'
        if "spacing" in ij_meta:
            print(f"Z spacing: {ij_meta['spacing']} {ij_meta.get('unit', 'pixels')}")
```

## Writing / Saving

### Save label mask as TIFF

**Input**: a label array (NumPy array of integers where each object has a unique ID, 0 = background).
**Output**: a TIFF file that can be opened in FIJI/ImageJ or reloaded in Python.

```python
import tifffile
import numpy as np

# `labels` is a 2D integer array from segmentation, e.g. shape (512, 512)
# Values: 0 = background, 1 = first object, 2 = second object, etc.

# Save as 32-bit integer TIFF (preserves label IDs even if > 255 objects)
tifffile.imwrite(
    "labels_mask.tif",
    labels.astype(np.int32),  # int32 supports up to ~2 billion unique labels
    compression="zlib",       # lossless compression to reduce file size
)
print(f"Saved label mask with {labels.max()} objects")
```

### Save overlay as PNG

**Input**: the original grayscale image and a label mask.
**Output**: a PNG file showing object outlines overlaid on the image (useful for quality control).

```python
import numpy as np
from skimage.io import imsave
from skimage.segmentation import find_boundaries
from skimage.exposure import rescale_intensity

# `image` is the original 2D grayscale image (e.g. uint16)
# `labels` is the 2D label mask from segmentation

# Step 1: normalize the grayscale image to 0–255 for display
image_normalized = rescale_intensity(image, out_range=(0, 255)).astype(np.uint8)

# Step 2: convert grayscale to RGB so we can draw colored outlines
overlay = np.stack([image_normalized] * 3, axis=-1)  # shape: (Y, X, 3)

# Step 3: find object boundaries (1-pixel-wide outlines)
boundaries = find_boundaries(labels, mode="outer")

# Step 4: draw boundaries in bright green (easy to see on most images)
overlay[boundaries, 0] = 0     # red channel
overlay[boundaries, 1] = 255   # green channel
overlay[boundaries, 2] = 0     # blue channel

# Step 5: save as PNG
imsave("overlay.png", overlay)
print(f"Saved overlay with {labels.max()} object outlines")
```

### Save measurements as CSV

**Input**: a label mask and the original image.
**Output**: a CSV file with one row per object and columns for area, intensity, etc.

```python
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table

# `image` is the original 2D grayscale image
# `labels` is the 2D label mask from segmentation
# `pixel_size_um` is the physical pixel size in micrometers (e.g. 0.65)
pixel_size_um = 0.65  # set this from metadata extraction above

# Step 1: measure properties for each labeled object
properties = regionprops_table(
    labels,
    intensity_image=image,
    properties=[
        "label",              # unique object ID
        "area",               # area in pixels
        "centroid",           # center coordinates (row, col)
        "mean_intensity",     # mean intensity inside the object
        "max_intensity",      # max intensity inside the object
        "eccentricity",       # 0 = circle, 1 = line (shape descriptor)
        "solidity",           # convexity measure (1 = perfectly convex)
    ],
)

# Step 2: convert to a pandas DataFrame
measurements_df = pd.DataFrame(properties)

# Step 3: rename columns for clarity and add physical units
measurements_df = measurements_df.rename(columns={
    "label": "object_id",
    "area": "area_px",
    "centroid-0": "centroid_y_px",
    "centroid-1": "centroid_x_px",
    "mean_intensity": "mean_intensity_au",     # "au" = arbitrary units
    "max_intensity": "max_intensity_au",
})

# Step 4: compute area in physical units (micrometers squared)
measurements_df["area_um2"] = measurements_df["area_px"] * (pixel_size_um ** 2)

# Step 5: save to CSV
measurements_df.to_csv("measurements.csv", index=False)
print(f"Saved measurements for {len(measurements_df)} objects")
print(measurements_df.head())
```
