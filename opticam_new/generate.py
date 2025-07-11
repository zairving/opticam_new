from astropy.io import fits
import os
from tqdm import tqdm
import numpy as np
from numpy.typing import NDArray
from typing import List


def __add_two_dimensional_gaussian_to_image(image: NDArray, x_centroid: float, y_centroid: float, peak_flux: float,
                                            sigma_x: float, sigma_y: float, theta: float) -> NDArray:
    """
    Add a source to an image.
    
    Parameters
    ----------
    image : NDArray
        The image.
    x_centroid : float
        The x-coordinate of the source.
    y_centroid : float
        The y-coordinate of the source.
    peak_flux : float
        The peak flux of the source.
    sigma_x : float
        The standard deviation of the source in the x-direction.
    sigma_y : float
        The standard deviation of the source in the y-direction.
    theta : float
        The rotation angle of the source.
    
    Returns
    -------
    NDArray
        The image with the source added.
    """
    
    x, y = np.meshgrid(np.arange(image.shape[1]), np.arange(image.shape[0]))
    
    a = np.cos(theta)**2/(2*sigma_x**2) + np.sin(theta)**2/(2*sigma_y**2)
    b = -np.sin(2*theta)/(4*sigma_x**2) + np.sin(2*theta)/(4*sigma_y**2)
    c = np.sin(theta)**2/(2*sigma_x**2) + np.cos(theta)**2/(2*sigma_y**2)
    
    gaussian = peak_flux*np.exp(-(a*(x - x_centroid)**2 + 2*b*(x - x_centroid)*(y - y_centroid) + c*(y - y_centroid)**2))
    
    return image + gaussian

def __variable_function(i: float) -> float:
    """
    Create a variable flux.
    
    Parameters
    ----------
    i : float
        The time.
    
    Returns
    -------
    float
        The flux.
    """
    
    return 50 * np.sin(2 * np.pi * i * 0.2)

def __create_base_image(i: int, binning_scale: int) -> NDArray:
    
    rng = np.random.default_rng(i)
    
    base_image = np.zeros((int(2048 / binning_scale), int(2048 / binning_scale))) + 100  # create blank image
    noisy_image = base_image + np.sqrt(base_image) * rng.standard_normal(base_image.shape)  # add Poisson noise
    
    return noisy_image

def __create_images(out_dir: str, filters: List[str], N_sources: int, variable_source: int, source_positions: NDArray,
                 peak_fluxes: NDArray, i: int, binning_scale: int, circular_aperture: bool, overwrite: bool) -> None:
    """
    Create an image for each filter.
    
    Parameters
    ----------
    filters : List[str]
        The filters.
    N_sources : int
        The number of sources.
    variable_source : int
        The index of the variable source.
    source_positions : NDArray
        The positions of the sources.
    peak_fluxes : NDArray
        The peak fluxes of the sources.
    i : int
        The time.
    binning_scale : int
        The binning scale.
    circular_aperture : bool
        Whether to apply a circular aperture shadow to the image.
    overwrite : bool
        Whether to overwrite the image if it already exists.
    """
    
    for fltr in filters:
        
        if os.path.isfile(f"{out_dir}/{fltr}-band_image_{i}.fits") and not overwrite:
            continue
        
        noisy_image = __create_base_image(i, binning_scale)
        if circular_aperture:
            noisy_image = __apply_flat_field(noisy_image)  # apply circular aperture shadow
        
        # put sources in the image
        for j in range(N_sources):
            
            if j == variable_source:
                noisy_image = __add_two_dimensional_gaussian_to_image(noisy_image, *source_positions[j],
                                                                      peak_fluxes[j] + __variable_function(i), 1, 1, 0)
            else:
                noisy_image = __add_two_dimensional_gaussian_to_image(noisy_image, *source_positions[j], peak_fluxes[j],
                                                                      1, 1, 0)
        
        # create fits file
        hdu = fits.PrimaryHDU(noisy_image)
        hdu.header["FILTER"] = fltr
        hdu.header["BINNING"] = f'{binning_scale}x{binning_scale}'
        hdu.header["GAIN"] = 1.
        
        # create observation time
        hh = str(i // 3600).zfill(2)
        mm = str(i % 3600 // 60).zfill(2)
        ss = str(i % 60).zfill(2)
        hdu.header["UT"] = f"2024-01-01 {hh}:{mm}:{ss}"
        
        # save fits file
        try:
            hdu.writeto(f"{out_dir}/240101{fltr}{200000000 + i}o.fits.gz", overwrite=overwrite)
        except:
            pass

def __apply_flat_field(image: NDArray):
    
    # define mask to apply circular aperture
    x_mid, y_mid = image.shape[1] // 2, image.shape[0] // 2
    distance_from_centre = np.sqrt((x_mid - np.arange(image.shape[1]))**2 +
                                   (y_mid - np.arange(image.shape[0]))[:, np.newaxis]**2)
    radius = image.shape[0] // 2
    mask = distance_from_centre >= radius
    
    # create circular aperture shadow
    falloff = 1 / (distance_from_centre[mask] / radius)**2
    
    # apply circular aperture shadow
    image[mask] *= falloff
    
    return image

def __create_flats(out_dir: str, filters: list, i: int, binning_scale: int, overwrite: bool):
    
    for fltr in filters:
        
        if os.path.isfile(f"{out_dir}/{fltr}-band_image_{i}.fits") and not overwrite:
            continue
        
        noisy_image = __create_base_image(i, binning_scale)
        noisy_image = __apply_flat_field(noisy_image)  # apply circular aperture shadow
        
        # create fits file
        hdu = fits.PrimaryHDU(noisy_image)
        hdu.header["FILTER"] = fltr
        hdu.header["BINNING"] = f'{binning_scale}x{binning_scale}'
        hdu.header["GAIN"] = 1.
        
        # create observation time
        hh = str(i // 3600).zfill(2)
        mm = str(i % 3600 // 60).zfill(2)
        ss = str(i % 60).zfill(2)
        hdu.header["UT"] = f"2024-01-01 {hh}:{mm}:{ss}"
        
        # save fits file
        try:
            hdu.writeto(f"{out_dir}/{fltr}-band_flat_{i}.fits.gz", overwrite=overwrite)
        except:
            pass

def create_synthetic_flats(out_dir: str, n_flats: int = 5, overwrite: bool = False):
    """
    Create synthetic flat-field images for testing and following the tutorials.
    
    Parameters
    ----------
    out_dir : str
        The directory to save the data.
    n_flats : int, optional
        The number of flats per camera, by default 5.
    overwrite : bool, optional
        Whether to overwrite data if they currently exist, by default False.
    """
    
    # create directory if it does not exist
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    
    filters = ["g", "r", "i"]
    binning_scale = 8
    
    for i in range(n_flats):
        __create_flats(out_dir, filters, i, binning_scale, overwrite)

def create_synthetic_observations(out_dir: str, n_images: int = 100, circular_aperture: bool = True,
                                  overwrite: bool = False):
    """
    Create synthetic observation data for testing and following the tutorials.
    
    Parameters
    ----------
    out_dir : str
        The directory to save the data.
    n_images : int, optional
        The number of images to create, by default 100.
    circular_aperture : bool, optional
        Whether to apply a circular aperture shadow to the images, by default True.
    overwrite : bool, optional
        Whether to overwrite data if they currently exist, by default False.
    """
    
    # create directory if it does not exist
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    
    rng = np.random.default_rng(123)
    filters = ["g", "r", "i"]
    
    binning_scale = 8
    
    N_sources = 6
    source_positions = rng.uniform(0 + int(64 / binning_scale), int(2048 / binning_scale - 64 / binning_scale),
                                   (N_sources, 2))  # generate random source positions away from the edges
    peak_fluxes = rng.uniform(100, 1000, N_sources)  # generate random peak fluxes
    variable_source = 1
    
    for i in tqdm(range(n_images), desc="Creating synthetic observations"):
        __create_images(out_dir, filters, N_sources, variable_source, source_positions, peak_fluxes, i, binning_scale,
                        circular_aperture, overwrite)