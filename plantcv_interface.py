from PIL import Image
from plantcv import plantcv as pcv
import cv2
import numpy as np
import uuid
import os
from math import pi
# Ref: https://plantcv.readthedocs.io/en/latest/tutorials/vis_tutorial/

class plantcv_interface:
    # Pre-process the plant (Removes all non-green elements)
    # Inputs: Filename
    # Outputs: New Filename
    def prepare_image(filename):

        # Formats the filename inputted
        fix_name = os.getcwd() + os.sep + 'images' + os.sep + filename
        img = cv2.imread(fix_name)

        # Formats the new filename outputted
        new_img_name = str(uuid.uuid4()) + '.jpg'
        new_img = os.getcwd() + os.sep + 'images' + os.sep + new_img_name

        # Converts color to HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Creates a mask
        mask = cv2.inRange(hsv, (36, 30, 30,), (86, 255, 255))
        imask = mask > 0

        # Generates an image
        green = np.zeros_like(img, np.uint8)

        # Applies mask to Image
        green[imask] = img[imask]

        # Writes out the new image
        cv2.imwrite(new_img, green)

        return new_img_name

    # Extract data from image
    # Inputs: Filename, Image_Save Flag
    # Outputs: Dictionary of Image Data
    def info_image(filename, img_flag = '0', orig_name = ''):

        # Handles if save_images flag is set
        if(img_flag == '1'):
            
            # Generates a new directory
            name = os.getcwd() + os.sep + "images" + os.sep + filename[:-4]
            os.mkdir(name)

            # Handles PlantCV options
            pcv.params.debug = "print"
            pcv.params.debug_outdir = name

        try:
            # Formats the Filename
            fixed_filename = os.getcwd() + os.sep + 'images' + os.sep + filename
            img, path, unused = pcv.readimage(filename = fixed_filename)

            ############### Image Conversion ###############
            # Converts image from RGB to HSV
            split_image = pcv.rgb2gray_hsv(rgb_img = img, channel = 's')

            # Creates a binary image based on light
            binary_image = pcv.threshold.binary(gray_img = split_image, threshold = 85, max_value = 255, object_type='light')

            # Applies a median blur filter
            blurred_image = pcv.median_blur(gray_img = binary_image, ksize = 5)

            # Applies a gaussian blur filter
            gaussian_img = pcv.gaussian_blur(img = binary_image, ksize = (5, 5), sigma_x = 0, sigma_y = None)

            # Converts image from RGB to LAB
            # https://plantcv.readthedocs.io/en/latest/rgb2lab/
            grayscale_img = pcv.rgb2gray_lab(rgb_img = img, channel = 'b')

            ################# Binary Conversion & Thresholding #################
            # Creates a binary image based on light
            binary_image2 = pcv.threshold.binary(gray_img = grayscale_img, threshold = 160, max_value = 255, object_type = 'light')

            # Logically OR two binary images together
            combined_binary_image = pcv.logical_or(bin_img1 = split_image, bin_img2 = binary_image2)

            # Applies binary mask to image
            masked_image = pcv.apply_mask(img = img, mask = combined_binary_image, mask_color = 'white')

            # Converts image from RGB to LAB
            mask1 = pcv.rgb2gray_lab(rgb_img = masked_image, channel = 'a')
            mask2 = pcv.rgb2gray_lab(rgb_img = masked_image, channel = 'b')

            # Creates a binary image based on light or dark
            binary_image3 = pcv.threshold.binary(gray_img = mask1, threshold = 115, max_value = 255, object_type = 'dark')
            binary_image4 = pcv.threshold.binary(gray_img = mask1, threshold = 135, max_value = 255, object_type = 'light')
            binary_image5 = pcv.threshold.binary(gray_img = mask2, threshold = 128, max_value = 255, object_type = 'light')

            # Logically OR three binary images together
            combined_binary_image2 = pcv.logical_or(bin_img1 = binary_image3, bin_img2 = binary_image5)
            combined_binary_image3 = pcv.logical_or(bin_img1 = binary_image4, bin_img2 = combined_binary_image2)

            # Filters out bright noise from an image
            filtered_image = pcv.opening(gray_img = combined_binary_image3)

            # Logically XOR two binary images together
            xor_image = pcv.logical_xor(bin_img1 = binary_image3, bin_img2 = binary_image5)

            # Identifies objects and fills objects that are less than specified size
            filled_image = pcv.fill(bin_img = combined_binary_image3, size = 200)

            # Filters out dark noise from an image
            filtered_image2 = pcv.closing(gray_img = filled_image)


            ############### Analysis ###############
            # Applies a binary mask to an image
            masked_image2 = pcv.apply_mask(img = masked_image, mask = filled_image, mask_color = 'white')

            # Detect objects within the image
            objects, object_hierachy = pcv.find_objects(img = masked_image2, mask = filled_image)

            # Combine objects together
            grouped_object, image_mask = pcv.object_composition(img = masked_image2, contours = objects, hierarchy = object_hierachy)

            # Shape Analysis
            analysis_image = pcv.analyze_object(img = masked_image2, obj = grouped_object, mask = image_mask, label = 'default')

            # Color Analysis
            pcv.analyze_color(rgb_img = masked_image2, mask = image_mask)

            ############### Output ##################
            # Output Width&Hieght
            width = pcv.outputs.observations['default']['width']['value']
            height = pcv.outputs.observations['default']['height']['value']
            
            orig_fixed_name = os.getcwd() + os.sep + 'images' + os.sep + orig_name

            ###### COUNT LEAVES ######
            img = cv2.imread(orig_fixed_name)

            # Convert the image to grayscale
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Apply Gaussian blur to reduce noise and improve contour detection
            blurred_img = cv2.GaussianBlur(gray_img, (5, 5), 0)

            # Use adaptive thresholding to create a binary image
            _, binary_img = cv2.threshold(blurred_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Find contours in the binary image
            contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Filter out small contours (noise) based on area
            min_contour_area = 1500  # Adjust this threshold as needed
            filtered_contours = [contour for contour in contours if cv2.contourArea(contour) > min_contour_area]

            # Select the largest contour (assumed to be the leaf)
            largest_leaf_contour = max(contours, key=cv2.contourArea)

            # Calculate leaf shape descriptors manually
            leaf_area = cv2.contourArea(largest_leaf_contour)
            perimeter = cv2.arcLength(largest_leaf_contour, True)
            circularity = (4 * pi * leaf_area) / (perimeter * perimeter)
            solidity = leaf_area / cv2.contourArea(cv2.convexHull(largest_leaf_contour))
            x, y, w, h = cv2.boundingRect(largest_leaf_contour)
            aspect_ratio = float(w) / h

            # Count the number of leaves (filtered contours)
            leaf_count = len(filtered_contours)

            pic_height, pic_width, _ = img.shape

            center_x = pic_width // 2
            center_y = pic_height // 2

            b, g, r = img[center_y, center_x]

            color = {
                "r" : int(r),
                "g" : int(g),
                "b" : int(b)
                }

            # Formats the Output
            return_data = {
                "width" : width,
                "height" : height,
                "color" : color,
                "leaf_count": leaf_count,
                "leaf_circ": circularity,
                "leaf_solid": solidity,
                "leaf_aspect": aspect_ratio
                }
            pcv.outputs.clear()
            return return_data

        # Handles if PlantCV fails
        except:
            return_data = {
                "width": 0,
                "height": 0,
                "color": {
                    "r": 0,
                    "g": 0,
                    "b": 0
                    },
                "leaf_count": 0,
                "leaf_circ": 0,
                "leaf_solid": 0,
                "leaf_aspect": 0
                }

            return return_data