"""
Bioimage analysis utility functions.

Callable decision logic for segmentation tool selection, version validation,
label post-processing, measurement pitfall detection, and memory estimation.

Usage: the LLM calls these functions during the analysis workflow to get
structured recommendations instead of interpreting prose decision trees.

Design:
- Every function imports its dependencies internally (never fails at module level)
- Returns dicts/tuples with structured data the LLM can act on
- No printing — the LLM formats output for the user
"""


def pick_segmentation_tool(object_type, modality="fluorescence",
                           objects_touching=True, shape="irregular"):
    """Pick segmentation tool based on object type, modality, and morphology.

    Parameters
    ----------
    object_type : str
        "nuclei", "whole_cells", "other", or "simple_binary"
    modality : str
        "fluorescence", "brightfield", "phase_contrast", "histology_he"
    objects_touching : bool
        Whether objects are touching/overlapping
    shape : str
        "round", "irregular", "unusual" (for object_type="other")

    Returns
    -------
    dict with keys:
        tool : str — primary tool name
        model : str — pretrained model name (or None)
        fallback_tool : str — what to try if primary fails
        fallback_model : str — fallback model name (or None)
        params : dict — key parameters to set
        notes : str — brief guidance
    """
    result = {"tool": None, "model": None, "fallback_tool": None,
              "fallback_model": None, "params": {}, "notes": ""}

    object_type = object_type.lower().replace(" ", "_").replace("-", "_")
    modality = modality.lower().replace(" ", "_").replace("-", "_")

    # --- Nuclei ---
    if object_type == "nuclei":
        if modality == "histology_he":
            result["tool"] = "stardist"
            result["model"] = "2D_versatile_he"
            result["fallback_tool"] = "cellpose"
            result["fallback_model"] = "nuclei"
            result["params"] = {"prob_thresh": 0.5, "nms_thresh": 0.3}
            result["notes"] = ("StarDist H&E model. If results are poor, "
                               "fall back to Cellpose nuclei model.")
        elif not objects_touching:
            result["tool"] = "threshold"
            result["model"] = None
            result["fallback_tool"] = "stardist"
            result["fallback_model"] = "2D_versatile_fluo"
            result["params"] = {"method": "otsu"}
            result["notes"] = ("Non-touching nuclei: Otsu threshold + "
                               "connected components is simplest. Fall back "
                               "to StarDist if thresholding merges objects.")
        else:
            result["tool"] = "stardist"
            result["model"] = "2D_versatile_fluo"
            result["fallback_tool"] = "cellpose"
            result["fallback_model"] = "nuclei"
            result["params"] = {"prob_thresh": 0.5, "nms_thresh": 0.3}
            result["notes"] = ("Touching fluorescent nuclei: StarDist is fast "
                               "and accurate. Fall back to Cellpose nuclei "
                               "if StarDist misses faint objects.")

    # --- Whole cells ---
    elif object_type == "whole_cells":
        if modality in ("brightfield", "phase_contrast"):
            result["tool"] = "cellpose"
            result["model"] = "livecell"
            result["fallback_tool"] = "cellpose"
            result["fallback_model"] = "cyto3"
            result["params"] = {"diameter": None, "channels": [0, 0]}
            result["notes"] = ("Brightfield/phase cells: livecell model trained "
                               "on diverse cell lines. Set diameter=None for auto. "
                               "Fall back to cyto3 if livecell fails.")
        else:
            result["tool"] = "cellpose"
            result["model"] = "cyto3"
            result["fallback_tool"] = "watershed"
            result["fallback_model"] = None
            result["params"] = {"diameter": None, "channels": [0, 0]}
            result["notes"] = ("Fluorescent whole cells: cyto3 handles irregular "
                               "shapes. Measure ~5 objects to set diameter manually "
                               "if auto is off. Fall back to membrane threshold + "
                               "watershed.")

    # --- Other objects ---
    elif object_type == "other":
        if shape == "round":
            result["tool"] = "stardist"
            result["model"] = "2D_versatile_fluo"
            result["fallback_tool"] = "cellpose"
            result["fallback_model"] = "cyto3"
            result["params"] = {"prob_thresh": 0.5, "nms_thresh": 0.3}
            result["notes"] = ("Round/convex objects: StarDist works well. May "
                               "need custom training if objects differ from "
                               "training data.")
        elif shape == "unusual":
            result["tool"] = "nnunetv2"
            result["model"] = None
            result["fallback_tool"] = "cellpose"
            result["fallback_model"] = "cyto3"
            result["params"] = {}
            result["notes"] = ("Very unusual morphology: nnUNetv2 with custom "
                               "training data. Requires 50+ annotated images. "
                               "Try Cellpose cyto3 first as a quick test.")
        else:  # irregular
            result["tool"] = "cellpose"
            result["model"] = "cyto3"
            result["fallback_tool"] = "nnunetv2"
            result["fallback_model"] = None
            result["params"] = {"diameter": None, "channels": [0, 0]}
            result["notes"] = ("Irregular objects: Cellpose cyto3. If it fails, "
                               "consider nnUNetv2 with custom training.")

    # --- Simple binary ---
    elif object_type == "simple_binary":
        if objects_touching:
            result["tool"] = "watershed"
            result["model"] = None
            result["fallback_tool"] = "cellpose"
            result["fallback_model"] = "cyto3"
            result["params"] = {"method": "threshold_then_watershed"}
            result["notes"] = ("Touching high-contrast objects: threshold + "
                               "distance transform + watershed. Fall back to "
                               "Cellpose if watershed over-segments.")
        else:
            result["tool"] = "threshold"
            result["model"] = None
            result["fallback_tool"] = "watershed"
            result["fallback_model"] = None
            result["params"] = {"method": "otsu"}
            result["notes"] = ("High contrast, non-touching: Otsu threshold + "
                               "connected components. Simplest approach.")

    else:
        result["tool"] = "cellpose"
        result["model"] = "cyto3"
        result["fallback_tool"] = "stardist"
        result["fallback_model"] = "2D_versatile_fluo"
        result["params"] = {"diameter": None}
        result["notes"] = (f"Unrecognized object_type '{object_type}'. "
                           "Defaulting to Cellpose cyto3 as general-purpose.")

    return result


def validate_model_for_version(tool_name, model_name):
    """Check if a model name is valid for the installed version of a tool.

    Parameters
    ----------
    tool_name : str
        "cellpose", "stardist", "nnunet", "bioio", "aicsimageio"
    model_name : str
        Model or package name to validate

    Returns
    -------
    dict with keys:
        valid : bool
        message : str — explanation
        suggestion : str or None — what to use instead
    """
    tool = tool_name.lower().strip()
    model = (model_name or "").strip()

    # --- Cellpose version checks ---
    if tool == "cellpose":
        cellpose_version = _get_version("cellpose")
        if cellpose_version is None:
            return {"valid": False,
                    "message": "Cellpose is not installed.",
                    "suggestion": "Install cellpose first."}

        major = _major_version(cellpose_version)

        if model == "cyto3" and major is not None and major < 3:
            return {"valid": False,
                    "message": (f"Cellpose {cellpose_version} does not have "
                                "cyto3. That model was added in Cellpose 3.x."),
                    "suggestion": "cyto2"}

        if major is not None and major >= 4:
            return {"valid": True,
                    "message": (f"Cellpose {cellpose_version} (4.x) has a new "
                                "architecture. Old model names may not work. "
                                "Check Cellpose docs for current model names."),
                    "suggestion": None}

    # --- nnUNet v1 vs v2 ---
    elif tool in ("nnunet", "nnunetv2"):
        v2 = _get_version("nnunetv2")
        v1 = _get_version("nnunet")
        if v2:
            return {"valid": True,
                    "message": f"nnUNetv2 {v2} installed. Use v2 CLI and dataset format.",
                    "suggestion": None}
        elif v1:
            return {"valid": False,
                    "message": (f"nnUNet v1 ({v1}) installed, not v2. "
                                "CLI and dataset format are completely different."),
                    "suggestion": "Install nnunetv2 for the current API."}
        else:
            return {"valid": False,
                    "message": "Neither nnunet nor nnunetv2 is installed.",
                    "suggestion": "Install nnunetv2."}

    # --- aicsimageio → bioio rename ---
    elif tool in ("bioio", "aicsimageio"):
        bioio = _get_version("bioio")
        aics = _get_version("aicsimageio")
        if not bioio and not aics:
            return {"valid": False,
                    "message": "Neither bioio nor aicsimageio is installed.",
                    "suggestion": "Install bioio (the current package)."}
        if tool == "aicsimageio" and bioio and not aics:
            return {"valid": False,
                    "message": ("aicsimageio has been renamed to bioio. "
                                f"bioio {bioio} is installed."),
                    "suggestion": "Use 'import bioio' instead of 'import aicsimageio'."}
        if tool == "bioio" and aics and not bioio:
            return {"valid": False,
                    "message": (f"aicsimageio {aics} is installed (the old name). "
                                "bioio is the current package."),
                    "suggestion": "Use 'import aicsimageio' or install bioio."}
        if tool == "bioio" and bioio:
            return {"valid": True,
                    "message": f"bioio {bioio} installed.",
                    "suggestion": None}
        if tool == "aicsimageio" and aics:
            return {"valid": True,
                    "message": (f"aicsimageio {aics} installed. Note: bioio is the "
                                "current name. aicsimageio still works."),
                    "suggestion": None}

    # --- StarDist (stable across versions) ---
    elif tool == "stardist":
        v = _get_version("stardist")
        if v is None:
            return {"valid": False,
                    "message": "StarDist is not installed.",
                    "suggestion": "Install stardist."}
        return {"valid": True,
                "message": f"StarDist {v}. Pretrained models are stable across versions.",
                "suggestion": None}

    return {"valid": True, "message": "No known compatibility issues.", "suggestion": None}


def _get_version(package_name):
    """Get installed version of a package. Returns None if not installed."""
    try:
        import importlib.metadata
        return importlib.metadata.version(package_name)
    except Exception:
        return None


def _major_version(version_string):
    """Extract major version number from a version string."""
    try:
        return int(version_string.split(".")[0])
    except (ValueError, IndexError, AttributeError):
        return None


def clean_labels(labels, remove_border=True, min_area_fraction=0.3,
                 min_area_absolute=None):
    """Post-process a label image: remove border objects and small fragments.

    Parameters
    ----------
    labels : ndarray
        Integer label image (0 = background, >0 = object IDs)
    remove_border : bool
        Remove objects touching the image border
    min_area_fraction : float
        Remove objects smaller than this fraction of median area.
        Set to 0 to skip area filtering.
    min_area_absolute : int or None
        If set, use this as absolute minimum area (pixels) instead of
        fraction-of-median.

    Returns
    -------
    (cleaned_labels, stats) where stats is a dict with:
        n_before, n_after, n_border_removed, n_small_removed
    """
    from skimage.segmentation import clear_border
    from skimage.measure import regionprops, label as relabel
    import numpy as np

    n_before = len(set(labels.ravel()) - {0})
    n_border_removed = 0
    n_small_removed = 0

    # Remove border objects
    if remove_border:
        labels_clean = clear_border(labels)
        n_after_border = len(set(labels_clean.ravel()) - {0})
        n_border_removed = n_before - n_after_border
        labels = labels_clean

    labels = relabel(labels > 0, connectivity=1)

    # Remove small objects
    if min_area_fraction > 0 or min_area_absolute is not None:
        regions = regionprops(labels)
        areas = [r.area for r in regions]
        if areas:
            if min_area_absolute is not None:
                min_area = min_area_absolute
            else:
                min_area = int(np.median(areas) * min_area_fraction)

            # Vectorized removal: build a lookup table instead of
            # scanning the full array once per small object
            max_label = int(labels.max())
            keep = np.ones(max_label + 1, dtype=bool)
            keep[0] = False  # background stays 0
            for region in regions:
                if region.area < min_area:
                    keep[region.label] = False
                    n_small_removed += 1

            if n_small_removed > 0:
                # Zero out all removed labels in one pass
                lut = np.zeros(max_label + 1, dtype=labels.dtype)
                for i in range(1, max_label + 1):
                    if keep[i]:
                        lut[i] = i
                labels = lut[labels]

            labels = relabel(labels > 0, connectivity=1)

    n_after = int(labels.max())
    stats = {
        "n_before": int(n_before),
        "n_after": n_after,
        "n_border_removed": int(n_border_removed),
        "n_small_removed": int(n_small_removed),
    }
    return labels, stats


def detect_measurement_pitfalls(labels, image, pixel_size_um=None,
                                is_timelapse=False):
    """Check for common measurement pitfalls before extracting measurements.

    Parameters
    ----------
    labels : ndarray
        Integer label image
    image : ndarray
        Intensity image (same shape as labels)
    pixel_size_um : float or None
        Pixel size in micrometers. None = uncalibrated.
    is_timelapse : bool
        Whether this is part of a timelapse series

    Returns
    -------
    list of dicts, each with:
        pitfall : str — name
        detected : bool — whether the issue was found
        severity : str — "warning" or "critical"
        message : str — explanation
        fix : str — what to do about it
    """
    import numpy as np
    from skimage.measure import regionprops

    pitfalls = []

    # 1. Edge objects present
    border_mask = np.zeros(labels.shape, dtype=bool)
    border_mask[0, :] = True
    border_mask[-1, :] = True
    border_mask[:, 0] = True
    border_mask[:, -1] = True
    border_labels = set(labels[border_mask]) - {0}
    has_edge = len(border_labels) > 0

    pitfalls.append({
        "pitfall": "edge_objects",
        "detected": has_edge,
        "severity": "warning",
        "message": (f"{len(border_labels)} objects touch the image border. "
                    "Their area, perimeter, and shape are truncated."
                    if has_edge else "No edge objects detected."),
        "fix": ("Use clean_labels(remove_border=True) or exclude from shape/"
                "intensity measurements. Keep for counting if needed."
                if has_edge else ""),
    })

    # 2. Saturation / clipping
    if np.issubdtype(image.dtype, np.integer):
        max_val = np.iinfo(image.dtype).max
    else:
        max_val = None  # skip saturation check for float images

    if max_val is not None:
        n_saturated = np.sum(image >= max_val)
        frac_saturated = n_saturated / image.size
        is_saturated = frac_saturated > 0.001  # >0.1% of pixels at max

        pitfalls.append({
            "pitfall": "saturation",
            "detected": is_saturated,
            "severity": "critical" if is_saturated else "warning",
            "message": (f"{frac_saturated:.2%} of pixels at max value ({max_val}). "
                        "Intensity measurements are underestimated for bright objects."
                        if is_saturated else "No saturation detected."),
            "fix": ("Check histogram for spike at max. If saturated, intensity "
                    "comparisons are unreliable for bright objects. Consider "
                    "re-imaging with lower exposure." if is_saturated else ""),
        })

    # 3. Missing calibration
    has_calibration = pixel_size_um is not None and pixel_size_um > 0
    pitfalls.append({
        "pitfall": "missing_calibration",
        "detected": not has_calibration,
        "severity": "critical",
        "message": ("No pixel size calibration provided. Area and distance "
                    "measurements will be in pixels, not micrometers."
                    if not has_calibration else
                    f"Calibrated: {pixel_size_um} um/pixel."),
        "fix": ("Set pixel_size_um from image metadata or measure a known "
                "structure. Required for cross-experiment comparison."
                if not has_calibration else ""),
    })

    # 4. Background subtraction reminder
    pitfalls.append({
        "pitfall": "background_subtraction",
        "detected": True,  # always flag as reminder
        "severity": "warning",
        "message": ("Reminder: verify whether background subtraction is needed. "
                    "If background is spatially heterogeneous, use local background "
                    "subtraction with an annular region around each object."),
        "fix": ("Measure intensity in a dilated annular region around each object "
                "(skimage.segmentation.expand_labels), then subtract."),
    })

    # 5. Photobleaching for timelapse
    if is_timelapse:
        pitfalls.append({
            "pitfall": "photobleaching",
            "detected": True,  # always flag for timelapse
            "severity": "warning",
            "message": ("Timelapse: intensity drops over time due to "
                        "photobleaching. Raw intensity trends are unreliable."),
            "fix": ("Normalize per-frame by dividing by median background "
                    "intensity. This removes the bleaching trend."),
        })

    # 6. Segmentation quality — check for suspiciously large/small objects
    regions = regionprops(labels)
    if len(regions) > 5:
        areas = [r.area for r in regions]
        median_area = np.median(areas)
        max_area = max(areas)
        if max_area > median_area * 10:
            pitfalls.append({
                "pitfall": "merged_objects",
                "detected": True,
                "severity": "warning",
                "message": (f"Largest object is {max_area/median_area:.0f}x median "
                            "area. Likely merged/under-segmented objects."),
                "fix": ("Overlay masks on the image and check large objects. "
                        "May need to re-run segmentation with different parameters."),
            })

    return pitfalls


def estimate_memory(shape, dtype="uint16", n_arrays=3):
    """Estimate peak RAM usage for loading and processing an image.

    Parameters
    ----------
    shape : tuple
        Image dimensions, e.g. (2048, 2048) or (100, 50, 2048, 2048)
    dtype : str
        Data type, e.g. "uint16", "uint8", "float32"
    n_arrays : int
        Number of arrays in memory simultaneously.
        Default 3: raw image + label image + one working copy.

    Returns
    -------
    dict with keys:
        size_gb : float — size of one array
        peak_gb : float — estimated peak with n_arrays
        fits_in_ram : bool — True if peak < 50% of available RAM
        available_ram_gb : float — detected system RAM
        warning : str — guidance if too large (empty if fits)
    """
    # Calculate single array size
    dtype_sizes = {
        "uint8": 1, "int8": 1, "uint16": 2, "int16": 2,
        "uint32": 4, "int32": 4, "float32": 4, "float64": 8,
        "uint64": 8, "int64": 8,
    }
    itemsize = dtype_sizes.get(str(dtype).lower(), 2)  # default to 2 (uint16)
    n_elements = 1
    for dim in shape:
        n_elements *= dim
    size_bytes = n_elements * itemsize
    size_gb = size_bytes / (1024 ** 3)
    peak_gb = size_gb * n_arrays

    # Detect available RAM
    available_ram_gb = _get_available_ram_gb()

    fits = peak_gb < (available_ram_gb * 0.5) if available_ram_gb else None

    warning = ""
    if fits is False:
        ndim = len(shape)
        if ndim == 2 and size_gb > 1:
            warning = (f"Single 2D image is {size_gb:.1f} GB — too large to load "
                       "whole. Use tiled processing: read tiles with tifffile or "
                       "openslide, process each tile, stitch labels. "
                       "See references/cookbook-pipeline.md Pipeline 4.")
        elif ndim >= 3:
            warning = (f"Full volume/stack is {size_gb:.1f} GB — too large to load "
                       "whole. Process one plane or timepoint at a time. "
                       "See references/cookbook-pipeline.md Pipeline 5.")
        else:
            warning = (f"Estimated peak memory {peak_gb:.1f} GB exceeds available "
                       f"RAM ({available_ram_gb:.1f} GB). Consider processing in "
                       "chunks or reducing data size.")

    return {
        "size_gb": round(size_gb, 3),
        "peak_gb": round(peak_gb, 3),
        "fits_in_ram": fits,
        "available_ram_gb": round(available_ram_gb, 1) if available_ram_gb else None,
        "warning": warning,
    }


def _get_available_ram_gb():
    """Get total system RAM in GB. Returns None if detection fails."""
    try:
        import os
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if pages > 0 and page_size > 0:
                return (pages * page_size) / (1024 ** 3)
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 ** 2)  # kB to GB
    except Exception:
        pass
    return None
