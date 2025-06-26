from astropy.io import fits
import numpy as np
from PyQt6.QtGui import QImage, QPixmap
import os

HOME = os.getenv("HOME")

def fits_to_qpixmap(fits_path: str, hdu_index: int = 0) -> QPixmap:
    # Step 1: Open FITS file
    with fits.open(fits_path) as hdul:
        data = hdul[hdu_index].data

    # Handle 2D image only
    if data is None or data.ndim != 2:
        raise ValueError("FITS file does not contain a 2D image.")

    # Step 2: Normalize to 0-255
    data = np.nan_to_num(data)  # Replace NaNs and infs with 0
    data_min = np.min(data)
    data_max = np.max(data)
    if data_max == data_min:
        norm_data = np.zeros_like(data, dtype=np.uint8)
    else:
        norm_data = 255 * (data - data_min) / (data_max - data_min)
        norm_data = norm_data.astype(np.uint8)

    # Step 3: Convert to QImage (grayscale format)
    height, width = norm_data.shape
    bytes_per_line = width
    qimg = QImage(
        norm_data.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8
    )

    # Step 4: Convert to QPixmap
    return QPixmap.fromImage(qimg)
