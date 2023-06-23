import os
import csv
import random
from datetime import datetime, timedelta
from time import sleep
from pathlib import Path
from PIL import Image

from picamera import PiCamera
from sense_hat import SenseHat

from orbit import ISS
from skyfield.api import load

# Function to convert a `skyfield` Angle to an EXIF-appropriate
# representation (rationals)
#   e.g. 98° 34' 58.7 to "98/1,34/1,587/10"
# Return a tuple containing a boolean and the converted angle,
# with the boolean indicating if the angle is negative.
def convert(angle):
    sign, degrees, minutes, seconds = angle.signed_dms()
    exif_angle = f'{degrees:.0f}/1,{minutes:.0f}/1,{seconds*10:.0f}/10'
    return sign < 0, exif_angle

# Load de421.bsp file needed for ISS tracking
ephemeris = load('de421.bsp')

# Initialise video capture
vc = True

# Initialise path information and data file
baseFolder = Path(__file__).parent.resolve()
dataFile = baseFolder/'data.csv'
imgFolder = baseFolder/'images'

# Create folder images if does not exists
if (not os.path.exists('images')):
  os.mkdir('images')

  
# Initialise SenseHat
sense = SenseHat()
sense.clear()

# Initialise HQ camera
camera = PiCamera()
camera.resolution = (4056,3040)

# Create a CSV file for data capture
f = open(dataFile, 'w', buffering=1)
writer = csv.writer(f)

# Write the header of the CSV file
header = ("Date/time", "Latitude", "Longtitude", "Temperature", "Humidity", "Pressure", "Pitch", "Roll", "Yaw", "X", "Y", "Z")
writer.writerow(header)


# Initialise parameters for time calculation
startTime = datetime.now()
nowTime = datetime.now()
prevTime = nowTime

# Number of seconds between photo captures
maxSeconds = 8

# Used to calculate the total filesize for all images
sumFSize = 0
# Maximum filesize of all photos in MBytes
sumFSizeMAX = 2800

# Run the programm for 3 hours
while (nowTime < startTime + timedelta(hours=3)):
    
    # Obtain the current time `t`
    t = load.timescale().now()
    # Compute where the ISS is at time `t`
    position = ISS.at(t)
    # Compute the coordinates of the Earth location directly beneath the ISS
    location = position.subpoint()
    print(location)

    nowTime = datetime.now()
    if ISS.at(t).is_sunlit(ephemeris):
      print("In sunlight")

      # Convert the latitude and longitude to EXIF-appropriate representations
      south, exifLatitude = convert(location.latitude)
      west, exifLongitude = convert(location.longitude)

      # Set the EXIF tags specifying the current location
      camera.exif_tags['GPS.GPSLatitude'] = exifLatitude
      camera.exif_tags['GPS.GPSLatitudeRef'] = "S" if south else "N"
      camera.exif_tags['GPS.GPSLongitude'] = exifLongitude
      camera.exif_tags['GPS.GPSLongitudeRef'] = "W" if west else "E"

      # Create filename based on date and time
      # fileName = baseFolder/'images'/(stTime+'.jpg') ##### not working
      stTime = nowTime.strftime("%Y%m%d-%H%M%S")
      
      # Randomly capture only one video for 60 seconds
      r = random.randint(1, 20)
      if (vc == True) and (r == 1):
        #Set to False to avoid capture video again
        vc = False
        
        # Create filename based on date and time
        fileName = 'images/{0}.h264'.format(stTime)
        # Capture video for 60 seconds with quality 20 to reduce filesize
        camera.resolution = (1920,1080)
        camera.framerate = 30
        camera.start_recording(fileName, quality=20)
        sleep(60)
        camera.stop_recording()
        camera.resolution = (4056,3040)
      else:
        # Create filename based on date and time
        fileName = 'images/{0}.jpg'.format(stTime)

        # Capture a new photo with quality set to 90 for JPEG to reduce image size
        camera.capture(fileName, quality=90)
        img = Image.open(fileName)
        img.save(fileName, quality=90)

      print(fileName)

      # Calculate the total filesize of all photos
      # and delete the last one if exceeds the specified limit
      imgFSize = os.path.getsize(fileName) / (1024*1024) # Image size in MBytes
      sumFSize += imgFSize # Size of all images in MBytes
      print ('Images Size = ', round(imgFSize, 2), '   Total Size = ', round(sumFSize, 2))
      # Delete the last photo if exceeds the total allowed size for all photos
      if (sumFSize > sumFSizeMAX):
        os.remove(fileName)
        sumFSize -= imgFSize

    else:
      # ISS is on the dark side of earth. We do not have to capture photos
      print("In darkness")



    # Capture data from sense HAT
    temperature = sense.get_temperature()
    humidity = sense.get_humidity()
    pressure = sense.get_pressure()
    orientation = sense.get_orientation()
    pitch = orientation['pitch']
    roll = orientation['roll']
    yaw = orientation['yaw']
    acceleration = sense.get_accelerometer_raw()
    x = acceleration['x']
    y = acceleration['y']
    z = acceleration['z']
    
    # Save information on the CSV file
    row = (datetime.now(), location.latitude, location.longitude, round(temperature, 2), round(humidity, 2), round(pressure, 2), round(pitch, 2), round(roll, 2), round(yaw, 2), round(x, 2), round(y, 2), round(z, 2))
    writer.writerow(row)
    
    # Print information
    print("time = :.", datetime.now(), " temperature = ", round(temperature, 2), " humidity = ", round(humidity, 2), " pressure = ", round(pressure, 2), " pitch = ", round(pitch, 2), " roll = ", round(roll, 2), " yaw = ", round(yaw, 2), " x = ", round(x, 2), " y = ", round(y, 2), " z = ", round(z, 2))

    # Calculate time for the next capture
    nowTime = datetime.now()
    sleepTime = maxSeconds - (nowTime - prevTime).seconds
    if sleepTime < 0 :  # To avoid negative values in case we have a mistake in the equation
      sleepTime = 0
    if sleepTime > maxSeconds :  # To avoid big values in case we have a wrong equation
      sleepTime = maxSeconds
    sleep(sleepTime)
    prevTime = datetime.now()
    
    
# Finalise
camera.close()  
sense.clear()
