import cv2
import numpy as np
import time  # Import time for FPS calculation
import math

# Pre-calculate zones to exclude from drawing lines
def calculate_nozone(shape, offset=50):
    y, x = shape[:2]
    y_nozone = list(range(y - offset, y + 1)) + list(range(0, offset + 1))
    x_nozone = list(range(x - offset, x + 1)) + list(range(0, offset + 1))
    return y_nozone, x_nozone

# Function to calculate and display FPS
def calculate_fps(prev_frame_time, new_frame_time, frame, position=(7, 70), font_scale=3, color=(100, 255, 0), thickness=3):
    font = cv2.FONT_HERSHEY_SIMPLEX
    # Calculate FPS
    fps = 1 / (new_frame_time - prev_frame_time)
    prev_frame_time = new_frame_time
    fps_text = str(int(fps))  # Convert FPS to an integer and then to string
    # Put FPS text on the frame
    cv2.putText(frame, fps_text, position, font, font_scale, color, thickness, cv2.LINE_AA)
    return prev_frame_time

# function to compute distance between 2 points
def distance(pt1, pt2):
    (x1, y1), (x2, y2) = pt1, pt2
    dist = math.sqrt( (x2 - x1)**2 + (y2 - y1)**2 )
    return dist

# Open the video file
cap = cv2.VideoCapture(r"C:\Users\ricbe\Documents\CODES\opcv-Tests\videolineas.mp4")
# Check if the video opened successfully
if not cap.isOpened():
    print("Error: Could not open the video.")
    exit()

# Predefined kernel for morphological operations
kernel = np.ones((5, 5), np.uint8)
white_kernel = np.ones((5, 5), np.uint8)
kernel2 = np.ones((5, 5), np.uint8)

# used to record the time when we processed last frame 
prev_frame_time = 0

# Pre-calculate zones to exclude from drawing lines
def calculate_nozone(shape, offset=50):
    y, x = shape[:2]
    y_nozone = list(range(y - offset, y + 1)) + list(range(0, offset + 1))
    x_nozone = list(range(x - offset, x + 1)) + list(range(0, offset + 1))
    return y_nozone, x_nozone

# Loop to read frames
while True:
    ret, orig_frame = cap.read()
    
    if not ret:
        break

    # Start measuring time for each frame
    new_frame_time = time.time()
    
    # Calculate zones for the current frame
    yimg_nozone, ximg_nozone = calculate_nozone(orig_frame.shape)
    
    # Blur and convert to grayscale
    blurred = cv2.GaussianBlur(orig_frame, (9, 9), 0)
    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
    
    # Thresholding for white mask
    _, white_msk = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    white_msk = cv2.dilate(white_msk, white_kernel, iterations=2)
    
    # Convert to LAB color space to detect field lines
    lab_frame = cv2.cvtColor(orig_frame, cv2.COLOR_BGR2LAB)
    lower_green = np.array([0, 0, 100])  # Lower bound for green
    upper_green = np.array([185, 125, 180])  # Upper bound for green
    mask_green = cv2.inRange(lab_frame, lower_green, upper_green)
    
    # Morphological transformations to clean up the mask
    opening = cv2.morphologyEx(mask_green, cv2.MORPH_OPEN, kernel, iterations=1)
    
    # Sure background
    sure_bg = cv2.erode(opening, kernel, iterations=2)
    sure_bg = cv2.dilate(sure_bg, kernel, iterations=2)
    
    # Adaptive thresholding to detect contours
    thresh = cv2.adaptiveThreshold(sure_bg, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, blockSize=5, C=0)
    
    # Find contours of the field markings
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Draw only large contours
    dummy_mask = np.zeros_like(mask_green)
    large_contours = [c for c in contours if cv2.contourArea(c) > 100000]
    cv2.drawContours(dummy_mask, large_contours, -1, (255, 255, 255), 2)
    
    # Morphological closing to refine mask
    #adap_thrs_morph = cv2.morphologyEx(dummy_mask, cv2.MORPH_CLOSE, kernel2, iterations=1)
    
    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(dummy_mask, rho=2, theta=np.pi / 180, threshold=250,
                            minLineLength=25, maxLineGap=50)
    
    # Create a copy to draw lines on
    image_lines_thrs = orig_frame.copy()
    lines_thrs = np.zeros_like(dummy_mask)
    
    # Draw detected lines while avoiding no-line zones
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if (y1 not in yimg_nozone or y2 not in yimg_nozone) and (x1 not in ximg_nozone or x2 not in ximg_nozone):
                cv2.line(image_lines_thrs, (x1, y1), (x2, y2), (255, 0, 0), 10)  # Blue lines
                cv2.line(lines_thrs, (x1, y1), (x2, y2), (255, 0, 0), 10)
    
    # Mask lines with white areas
    lines_thrs = cv2.bitwise_and(lines_thrs, white_msk)
    
    # Create a colored mask for detected lines
    colored_mask = np.zeros_like(orig_frame)
    colored_mask[lines_thrs == 255] = [255, 0, 0]  # Blue lines
    
    # Overlay the colored mask on the original frame
    overlay_image = cv2.addWeighted(orig_frame, 1, colored_mask, 1, 0)

    # Calculate and display FPS
    prev_frame_time = calculate_fps(prev_frame_time, new_frame_time, overlay_image)
    
    # Display the combined frame
    #cv2.imshow('Combined Video', overlay_image)
    """
    Filter of the lines mask
    """
    colored_mask_blur = cv2.GaussianBlur(colored_mask, (9, 9), 0)
    colored_mask_filt = cv2.Laplacian(colored_mask_blur, ddepth=cv2.CV_16S, ksize=9)
    colored_mask_filt = cv2.convertScaleAbs(colored_mask_filt)
    #colored_mask_filt = colored_mask_blur # Line for easier debugging

    """
    Corner detection
    """
    gray_crn = cv2.cvtColor(colored_mask_filt,cv2.COLOR_BGR2GRAY)
    gray_crn = np.float32(gray_crn)
    dst = cv2.cornerHarris(gray_crn,2,3,0.04)
    #result is dilated for marking the corners, not important
    dst = cv2.dilate(dst,None)
    colored_mask_filt[dst>0.9*dst.max()]=[0,0,255] # number between dst and .max is the threshold for the corners considered
    """
    # Filtering corners
    mask = np.zeros_like(gray_crn)
    mask[dst>0.01*dst.max()] = 255
    # storing coordinate positions of all points in a list
    coordinates = np.argwhere(mask)
    coor_list = coordinates.tolist()
    
    # points beyond this threshold are preserved
    thresh = 20

    coor_list_2 = coor_list.copy()

    # iterate for every 2 points
    i = 1    
    for pt1 in coor_list:
        for pt2 in coor_list[i::1]:
            if(distance(pt1, pt2) < thresh):
                # to avoid removing a point if already removed
                try:
                    coor_list_2.remove(pt2)      
                except:
                    pass
        i+=1

    # draw final corners
    img2 = colored_mask.copy()
    for pt in coor_list_2:
        img2 = cv2.circle(img2, tuple(reversed(pt)), 3, (0, 0, 255), -1)

    #img[dst>0.01*dst.max()]=[0,0,255]#"""
    cv2.imshow('dst',colored_mask_filt)

    
    # Break loop if 'q' is pressed
    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

# Release video capture and close windows
cap.release()
cv2.destroyAllWindows()