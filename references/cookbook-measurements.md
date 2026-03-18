# Measurements Cookbook

Runnable patterns for extracting measurements from labeled images, exporting results,
and creating basic plots. Every code block includes complete imports and is ready to
copy-paste into a script or notebook.

---

## Morphology Measurements

### Basic regionprops (area, eccentricity, solidity, perimeter)

Extract shape descriptors from a labeled mask and collect them into a pandas DataFrame
in one step.

```python
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table

# labels: 2-D integer array where each object has a unique ID (0 = background)
labels = ...  # output from your segmentation step

# Extract morphology features into a DataFrame
morph_df = pd.DataFrame(regionprops_table(
    labels,
    properties=(
        "label",          # unique object ID
        "area",           # number of pixels in the object
        "eccentricity",   # 0 = circle, 1 = line
        "solidity",       # area / convex hull area (lower = more irregular)
        "perimeter",      # boundary length in pixels
    ),
))

print(morph_df.head())
#   label  area  eccentricity  solidity  perimeter
# 0     1   312          0.41      0.94       63.2
# 1     2   287          0.55      0.88       59.8
```

### Calibrated measurements (pixels to micrometers)

Raw pixel counts are meaningless for cross-experiment comparison. Always convert
using the pixel size from your image metadata.

```python
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table

labels = ...  # labeled mask from segmentation

# Pixel size in micrometers — check your image metadata or microscope settings.
# For .tif files, inspect with tifffile; for .czi/.nd2, use aicsimageio or nd2 reader.
# If metadata is missing, measure a known structure (scale bar, hemocytometer grid).
pixel_size_um = 0.325  # micrometers per pixel

# Extract raw pixel measurements
morph_df = pd.DataFrame(regionprops_table(
    labels,
    properties=("label", "area", "perimeter"),
))

# Convert to calibrated units
morph_df["area_um2"] = morph_df["area"] * (pixel_size_um ** 2)        # pixels -> um^2
morph_df["perimeter_um"] = morph_df["perimeter"] * pixel_size_um      # pixels -> um

# Drop raw pixel columns if you only want calibrated values
morph_df = morph_df.drop(columns=["area", "perimeter"])

print(morph_df.head())
#   label  area_um2  perimeter_um
# 0     1     32.96         20.54
# 1     2     30.32         19.44
```

---

## Intensity Measurements

### Mean, max, integrated intensity per object

Pass the raw intensity image alongside the label mask to `regionprops_table`.

```python
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table

labels = ...       # labeled mask (2-D integer array)
intensity = ...    # raw fluorescence image (same shape as labels, not preprocessed)

# Extract intensity features
intensity_df = pd.DataFrame(regionprops_table(
    labels,
    intensity_image=intensity,
    properties=(
        "label",
        "mean_intensity",       # average signal per pixel in the object
        "max_intensity",        # brightest pixel in the object
        "area",                 # needed to compute integrated intensity
    ),
))

# Integrated intensity = total signal in the object (accounts for object size)
intensity_df["integrated_intensity_au"] = (
    intensity_df["mean_intensity"] * intensity_df["area"]
)

# Rename for clarity
intensity_df = intensity_df.rename(columns={
    "mean_intensity": "mean_intensity_au",
    "max_intensity": "max_intensity_au",
})

print(intensity_df.head())
#   label  mean_intensity_au  max_intensity_au  area  integrated_intensity_au
# 0     1             1842.3            3104.0   312                574637.6
# 1     2             1567.8            2890.0   287                449958.6
```

### Multi-channel intensity (measure channel B using channel A labels)

A common pattern: segment nuclei in the DAPI channel, then measure marker
fluorescence in a different channel using those same nuclear masks.

```python
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table

# Channel A: used for segmentation (e.g., DAPI / nuclei)
# Channel B: marker to quantify (e.g., EdU, Ki67, GFP)
channel_a = ...    # 2-D array, used only for segmentation
channel_b = ...    # 2-D array, same spatial dimensions as channel_a
labels = ...       # labeled mask produced by segmenting channel_a

# Measure channel B intensity using channel A labels
multi_ch_df = pd.DataFrame(regionprops_table(
    labels,
    intensity_image=channel_b,       # <-- measure this channel
    properties=(
        "label",
        "mean_intensity",
        "max_intensity",
        "area",
    ),
))

# Rename columns to indicate which channel was measured
multi_ch_df = multi_ch_df.rename(columns={
    "mean_intensity": "mean_intensity_chB_au",
    "max_intensity": "max_intensity_chB_au",
})

print(multi_ch_df.head())
#   label  mean_intensity_chB_au  max_intensity_chB_au  area
# 0     1                  587.1                1204.0   312
# 1     2                  423.5                 980.0   287
```

### Background-subtracted intensity (annular region)

Measure local background in a ring (annulus) around each object by dilating the
label mask, then subtracting the original mask. This handles spatially varying
background (common in tissue sections and uneven illumination).

```python
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table
from skimage.segmentation import expand_labels

labels = ...       # labeled mask from segmentation
intensity = ...    # raw fluorescence image (same shape as labels)

# --- Step 1: Create dilated labels ---
# expand_labels grows each labeled region outward by `distance` pixels.
# Choose a dilation distance that captures nearby background without
# overlapping neighboring objects (5-10 px is a common starting point).
dilation_px = 5
dilated_labels = expand_labels(labels, distance=dilation_px)

# --- Step 2: Create annular (ring) mask ---
# The annulus is the dilated region minus the original object.
# Where the original label exists, zero it out so only the ring remains.
annular_labels = dilated_labels.copy()
annular_labels[labels > 0] = 0  # remove the object interior

# --- Step 3: Measure background intensity in the annular region ---
bg_df = pd.DataFrame(regionprops_table(
    annular_labels,
    intensity_image=intensity,
    properties=("label", "mean_intensity"),
))
bg_df = bg_df.rename(columns={"mean_intensity": "bg_mean_intensity"})

# --- Step 4: Measure object intensity ---
obj_df = pd.DataFrame(regionprops_table(
    labels,
    intensity_image=intensity,
    properties=("label", "mean_intensity"),
))

# --- Step 5: Subtract background ---
merged_df = obj_df.merge(bg_df, on="label", how="left")
merged_df["mean_intensity_bgsub_au"] = (
    merged_df["mean_intensity"] - merged_df["bg_mean_intensity"]
)

print(merged_df[["label", "mean_intensity", "bg_mean_intensity", "mean_intensity_bgsub_au"]].head())
#   label  mean_intensity  bg_mean_intensity  mean_intensity_bgsub_au
# 0     1          1842.3             1102.0                    740.3
# 1     2          1567.8              998.5                    569.3
```

---

## Spatial Measurements

### Nearest-neighbor distance

Compute the distance from each object's centroid to the closest neighboring
object. Useful for quantifying clustering or confluency.

```python
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table
from scipy.spatial import KDTree

labels = ...  # labeled mask

# Extract centroids
centroid_df = pd.DataFrame(regionprops_table(
    labels,
    properties=("label", "centroid"),
))
# regionprops_table names centroid columns "centroid-0" (row) and "centroid-1" (col)
coords = centroid_df[["centroid-0", "centroid-1"]].values  # shape (N, 2)

# Build a KD-tree for fast nearest-neighbor lookup
tree = KDTree(coords)

# Query the 2 nearest neighbors (first match is the point itself at distance 0)
distances, indices = tree.query(coords, k=2)
centroid_df["nn_distance_px"] = distances[:, 1]  # second column = nearest neighbor

# Convert to micrometers if calibrated
pixel_size_um = 0.325
centroid_df["nn_distance_um"] = centroid_df["nn_distance_px"] * pixel_size_um

print(centroid_df[["label", "nn_distance_um"]].head())
#   label  nn_distance_um
# 0     1           12.35
# 1     2            8.72
```

### Local density (neighbor count within radius)

Count how many objects fall within a given radius of each object's centroid.
Useful for assessing local microenvironment or paracrine signaling range.

```python
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table
from scipy.spatial import KDTree

labels = ...  # labeled mask

pixel_size_um = 0.325
radius_um = 50.0                             # biological radius of interest
radius_px = radius_um / pixel_size_um        # convert to pixels for the query

# Extract centroids
centroid_df = pd.DataFrame(regionprops_table(
    labels,
    properties=("label", "centroid"),
))
coords = centroid_df[["centroid-0", "centroid-1"]].values

# Count neighbors within radius (subtract 1 to exclude the point itself)
tree = KDTree(coords)
neighbor_counts = tree.query_ball_point(coords, r=radius_px)
centroid_df["neighbors_within_50um"] = [len(n) - 1 for n in neighbor_counts]

print(centroid_df[["label", "neighbors_within_50um"]].head())
#   label  neighbors_within_50um
# 0     1                      3
# 1     2                      5
```

---

## Export

### Measurements to CSV with units

Include units in column names so downstream analysis is unambiguous. This is
especially important when sharing data with collaborators.

```python
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table

labels = ...       # labeled mask
intensity = ...    # raw fluorescence image

pixel_size_um = 0.325

# Build a combined measurements DataFrame
props = pd.DataFrame(regionprops_table(
    labels,
    intensity_image=intensity,
    properties=(
        "label",
        "area",
        "eccentricity",
        "solidity",
        "perimeter",
        "mean_intensity",
        "max_intensity",
    ),
))

# Calibrate and rename with units
props["area_um2"] = props["area"] * (pixel_size_um ** 2)
props["perimeter_um"] = props["perimeter"] * pixel_size_um
props["integrated_intensity_au"] = props["mean_intensity"] * props["area"]
props = props.rename(columns={
    "mean_intensity": "mean_intensity_au",
    "max_intensity": "max_intensity_au",
})

# Keep only the columns with proper units
export_cols = [
    "label",
    "area_um2",
    "perimeter_um",
    "eccentricity",
    "solidity",
    "mean_intensity_au",
    "max_intensity_au",
    "integrated_intensity_au",
]
props[export_cols].to_csv("measurements.csv", index=False)

print(f"Exported {len(props)} objects to measurements.csv")
```

### Summary statistics table

Generate a per-condition summary (mean, SD, count) for reporting.

```python
import pandas as pd

# df: DataFrame with a "condition" column and measurement columns
# (e.g., from merging measurements with an experimental metadata table)
df = pd.read_csv("measurements.csv")
df["condition"] = ...  # assign condition labels (e.g., "control", "treated")

# Compute summary statistics grouped by condition
summary = (
    df.groupby("condition")["area_um2"]
    .agg(["count", "mean", "std", "median"])
    .rename(columns={
        "count": "n_objects",
        "mean": "mean_area_um2",
        "std": "sd_area_um2",
        "median": "median_area_um2",
    })
    .reset_index()
)

print(summary)
#   condition  n_objects  mean_area_um2  sd_area_um2  median_area_um2
# 0   control        142         245.3         42.1            238.7
# 1   treated        128         198.6         38.9            192.4

summary.to_csv("summary_statistics.csv", index=False)
```

---

## Basic Plots

All plots use matplotlib with publication-ready styling: labeled axes, readable
font sizes, and clean layouts.

### Box plot per condition

Compare a measurement across experimental conditions.

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("measurements.csv")
df["condition"] = ...  # assign condition labels

# Group data by condition for the box plot
conditions = df["condition"].unique()
data_by_condition = [df.loc[df["condition"] == c, "area_um2"] for c in conditions]

fig, ax = plt.subplots(figsize=(4, 5))
bp = ax.boxplot(data_by_condition, labels=conditions, patch_artist=True, widths=0.5)

# Style the boxes
for patch in bp["boxes"]:
    patch.set_facecolor("#B3CDE3")
    patch.set_edgecolor("black")

ax.set_ylabel("Cell area (\u00b5m\u00b2)", fontsize=12)
ax.set_xlabel("Condition", fontsize=12)
ax.tick_params(axis="both", labelsize=10)
ax.set_title("Cell area by condition", fontsize=13)

plt.tight_layout()
plt.savefig("boxplot_area.png", dpi=150)
plt.show()
```

### Histogram of areas

Visualize the distribution of object sizes.

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("measurements.csv")

fig, ax = plt.subplots(figsize=(5, 4))
ax.hist(df["area_um2"], bins=30, color="#7FCDBB", edgecolor="black", linewidth=0.5)

ax.set_xlabel("Cell area (\u00b5m\u00b2)", fontsize=12)
ax.set_ylabel("Count", fontsize=12)
ax.tick_params(axis="both", labelsize=10)
ax.set_title("Distribution of cell areas", fontsize=13)

plt.tight_layout()
plt.savefig("histogram_area.png", dpi=150)
plt.show()
```

### Scatter: area vs intensity

Explore the relationship between object size and fluorescence signal.

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("measurements.csv")

fig, ax = plt.subplots(figsize=(5, 5))
ax.scatter(
    df["area_um2"],
    df["mean_intensity_au"],
    s=15,                   # marker size
    alpha=0.5,              # transparency for overlapping points
    color="#2B8CBE",
    edgecolors="none",
)

ax.set_xlabel("Cell area (\u00b5m\u00b2)", fontsize=12)
ax.set_ylabel("Mean intensity (a.u.)", fontsize=12)
ax.tick_params(axis="both", labelsize=10)
ax.set_title("Area vs. mean intensity", fontsize=13)

plt.tight_layout()
plt.savefig("scatter_area_intensity.png", dpi=150)
plt.show()
```
