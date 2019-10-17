from PIL import Image
import openslide
import numpy as np
import cv2
import warnings
from matplotlib import pyplot as plt
import subprocess
import sys
import time
import math


def produce_edges_old(in_img, out_img, level):
    '''
    Takes as input an image and uses Canny edge detector from opencv
    library to produce an image in which the detected edges are marked.
    '''

    # read the image
    svs = openslide.OpenSlide(in_img)
    img = svs.read_region((0, 0), level, svs.level_dimensions[level])
    img = np.array(img.convert('RGB'))
    img = img[..., ::-1]

    # run Canny edge detector
    edges = cv2.Canny(img, 100, 200)

    # save the produced image in a ppm format
    edges = Image.fromarray(edges)
    warnings.filterwarnings("ignore")

    edges = edges.convert('RGB')
    edges.save(out_img, 'PPM')
    warnings.filterwarnings("default")


def downsample_image(svs, downsampling_factor, mode="numpy"):
    '''
    Takes an OpenSlide SVS object and downsamples the original resolution
    (level 0) by the requested downsampling factor, using the most convenient
    image level. Returns numpy array or PIL image.
    '''

    # Get the best level to quickly downsample the image
    # Add a pseudofactor of 0.1 to ensure getting the next
    # best level (i.e. if 16x is chosen, avoid getting 4x instead
    # of 16x)
    best_downsampling_level = svs.get_best_level_for_downsample(
        downsampling_factor + 0.1)

    # Get the image at the requested scale
    svs_native_levelimg = svs.read_region((0, 0),
                                          best_downsampling_level,
                                          svs.level_dimensions[best_downsampling_level])
    target_size = tuple([int(x//downsampling_factor) for x in svs.dimensions])
    img = svs_native_levelimg.resize(target_size)

    # By default, return numpy array,
    # otherwise, return PIL image
    if mode == "numpy":
        # Remove the alpha channel
        img = np.array(img.convert("RGB"))

    return img, best_downsampling_level


def produce_edges(in_img, out_img, downsampling_factor, verbose):
    '''
    Takes as input an image and uses Canny edge detector from opencv
    library to produce an image in which the detected edges are marked.
    '''

    print("== Step 1: Producing edge image... ==")
    ts = time.time()

    # Read the image
    svs = openslide.OpenSlide(in_img)
    img, bdl = downsample_image(svs, downsampling_factor)

    if verbose:
        print("Requested " + str(downsampling_factor) +
              "x downsampling for edge detection.")
        print("SVS level 0 dimensions:", svs.dimensions)
        print("Using level " + str(bdl) + " to downsample.")
        print("Downsampled size: " + str(img.shape[::-1][1:3]))

    # Run Canny edge detector
    edges = cv2.Canny(img, 100, 200)

    # Save the produced image in PPM format to feed to Felzenszwalb's algorithm
    edges = Image.fromarray(edges)
    warnings.filterwarnings("ignore")

    edges = edges.convert('RGB')
    edges.save(out_img, 'PPM')
    warnings.filterwarnings("default")
    te = time.time()

    if verbose:
        print("Elapsed time: " + str(te - ts))


def produce_test_image(image, out_folder, args):
    '''
    Produces a PNG version of the segmented PPM image overlaying the
    grid with the selected patch size at the output downscale resolution.
    '''

    print("Producing test image...")

    # Get information about arguments and image
    output_downsample = args.output_downsample
    patch_size = args.patch_size
    svs = openslide.OpenSlide(args.svs)
    image_dims = svs.dimensions  # (x, y)

    # Since we read an numpy array, we need to change BGR -> RGB
    mask = cv2.imread(out_folder + "segmented_" + image + ".ppm")  # (y, x)
    resized_mask = cv2.resize(mask, (image_dims[0]//output_downsample,
                                     image_dims[1]//output_downsample))

    # Draw a grid over the image (does thickness need to be 2?)
    x_shift, y_shift = patch_size, patch_size
    gcol = [255, 0, 0]
    resized_mask[:, ::y_shift, :] = gcol
    resized_mask[::x_shift, :, :] = gcol

    # The mask should have the scaling factor of the requested output image
    cv2.imwrite(out_folder + "test_" + image + ".png", resized_mask)


def produce_segmented_image(sample_id, out_folder, sigma, k_const,
                            min_segmentsize, verbose):
    '''
    Invokes a shell to run Felzenszwalb's algorithm with the PPM
    image containing the edges from the Canny detector.
    '''
    print("\n== Step 2: Running Felzenszwalb's algorithm over the mask ==")

    ts = time.time()
    bashCommand = "src/Felzenszwalb_algorithm/segment " + str(sigma) + " " + \
        str(k_const) + " " + str(min_segmentsize) + " " + out_folder + \
        "edges_" + sample_id + ".ppm" + " " + \
        out_folder + "segmented_" + sample_id + ".ppm"
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    te = time.time()

    if verbose:
        print("Elapsed time: " + str(te - ts))

    if error is not None:
        print(error)
        sys.exit(1)


def isPowerOfTwo(n):
    return math.ceil(math.log2(n)) == math.floor(math.log2(n))
