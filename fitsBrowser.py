#!/usr/bin/env python

import argparse, sys, os, re, json, shutil
import configHelper, numpy
import astropy
from astropy.io import fits
from PIL import Image,ImageDraw,ImageFont

debug = False

class imageObject:
	def __init__(self):
		self.filename = None
		self.size = (0, 0)
		self.imageData = None
		self.boostedImageExists = False
	
	def initFromFITSFile(self, filename, path="."):
		try:
			hdulist = fits.open(path + "/" + filename)
			if debug: print "Info: ", hdulist.info()
			card = hdulist[0]
			for h in hdulist:
				imageData = h.data
				if imageData!=None: 
					xSize, ySize = numpy.shape(imageData)
					if debug: print("Found image data of dimensions (%d, %d)"%(xSize, ySize))
					break
	
			hdulist.close()
		except: 
			print "Could not find any valid FITS data for %s"%filename
			return False
		
		if imageData!=None:
			self.imageData = imageData
			self.filename = filename
			self.size = (xSize, ySize)
		
		return True
		
	def getBoostedImage(self):
		""" Returns a normalised array where lo percent of the pixels are 0 and hi percent of the pixels are 255 """
		hi = 99
		lo = 20
		data = numpy.copy(self.imageData)
		max = data.max()
		dataArray = data.flatten()
		pHi = numpy.percentile(dataArray, hi)
		pLo = numpy.percentile(dataArray, lo)
		range = pHi - pLo
		scale = range/255
		data = numpy.clip(data, pLo, pHi)
		data-= pLo
		data/=scale
		self.boostedImage = data
		self.boostedImageExists = True
		return data
		
	def writeAsPNG(self, boosted=False, filename = None):
		imageData = numpy.copy(self.imageData)
		if boosted==True:
			if not self.boostedImageExists: imageData = self.getBoostedImage()
			else: imageData = self.boostedImage
		imgData = numpy.rot90(imageData, 3)
		imgSize = numpy.shape(imgData)
		imgLength = imgSize[0] * imgSize[1]
		testData = numpy.reshape(imgData, imgLength, order="F")
		img = Image.new("L", imgSize)
		palette = []
		for i in range(256):
			palette.extend((i, i, i)) # grey scale
			img.putpalette(palette)
		img.putdata(testData)
		
		if filename==None:
			outputFilename = changeExtension(self.filename, "png")
		else:
			outputFilename = filename
			
		if debug: print ("Writing PNG file: " + outputFilename) 
		img.save(outputFilename, "PNG", clobber=True)
		
	def createThumbnail(self, filename = None, size=128):
		if not self.boostedImageExists: imageData = self.getBoostedImage()
		else: imageData = self.boostedImage
		
		imgData = numpy.rot90(imageData, 3)
		imgSize = numpy.shape(imgData)
		imgLength = imgSize[0] * imgSize[1]
		testData = numpy.reshape(imgData, imgLength, order="F")
		img = Image.new("L", imgSize)
		palette = []
		for i in range(256):
			palette.extend((i, i, i)) # grey scale
			img.putpalette(palette)
		img.putdata(testData)
		thumbnailSize = (size, size)
		img.thumbnail(thumbnailSize, Image.ANTIALIAS)
		if filename==None:
			outputFilename = "thumb_" + changeExtension(self.filename, "png")
		else:
			outputFilename = filename
		
		if debug: print ("Writing thumbnail file: " + outputFilename) 
		img.save(outputFilename, "PNG", clobber=True)
		
	
def changeExtension(filename, extension):
	return os.path.splitext(filename)[0] + "." + extension 
	
if __name__ == "__main__":
	
	parser = argparse.ArgumentParser(description='Makes a web-browser accessible page containing previews and thumbnails of all FITS images in a directory.')
	parser.add_argument('--datapath', type=str, help='Path where the FITS files are. Default: current directory')
	parser.add_argument('--webpath', type=str, help='Path to write the web page and images to. Default: current directory')
	parser.add_argument('--installpath', type=str, help='Path of where this application has been installed. This is so that it can find the HTML files to copy to the web folder. ')
	parser.add_argument('--size', type=int, help='Thumbnail size. Default is 128 pixels.')
	parser.add_argument('--save', action="store_true", help='Write the input parameters to the config file as default values.')
	parser.add_argument('--skipallimages', action="store_true", help="Skip creating of the images and thumbnails, just create the metadata. (For debugging purposes)")
	parser.add_argument('--skipimages', action="store_true", help="Skip creating of the images (but still creates the thumbnails.")
	parser.add_argument('--html', action="store_true", help="Skip most of the work and just write the HTML pages to the destination folder. (creating of the images (but still creates the thumbnails.")
	parser.add_argument('-f', '--force', action="store_true", help="Force the re-creation of the PNG images and thumbnails. The default behaviour is to check the output folder to see if the PNG image already exists. If so, it skips the creation step. ")
	parser.add_argument('--debug', action="store_true", help="Show some debug information.")
	parser.add_argument('--headerlist', type=str, help='Filename of a text file containing FITS headers that should be displayed on the web page.')
	
	args = parser.parse_args()
	if args.debug: debug = True
	if debug: print(args)
	
	forceImages = False
	if args.force: forceImages = True
	
	skipthumbnails = False
	skipimages = False
	if args.skipallimages:
		skipthumbnails = True
		skipimages = True
	if args.skipimages == True: skipimages = True
	# if args.skipthumbnails == True: skipthumbnails = True
		
	
	config = configHelper.configClass("fitsBrowser")
	configDefaults  = {
		"FITSPath": ".",
		"SearchString": ".*.(fits|fits.gz|fits.fz|fit)",
		"WebPath": ".",
		"InstallPath": "undefined", 
		"ThumbnailSize": 128
	}
	config.setDefaults(configDefaults)
	rootPath = config.assertProperty("FITSPath", args.datapath)
	searchString = config.assertProperty("SearchString", None)
	webPath = config.assertProperty("WebPath", args.webpath)
	installPath = config.assertProperty("InstallPath", args.installpath)
	thumbnailSize = config.assertProperty("ThumbnailSize", args.size)
	if args.save:
		config.save()
	
	print "Install path:", installPath
	if installPath == "undefined": 
		print "Please specify the install path of fitsBrowser. Use the --installpath command option, or specify it in ~/.config/fitsBrowser/fitsBrowser.conf file."
		sys.exit(-1)
	
	search_re = re.compile(searchString)
	
	# Create sub-folder for the images
	imageFolder = webPath + "/images"
	if debug: print "Creating folder %s"%imageFolder
	if not os.path.exists(imageFolder):
		os.makedirs(imageFolder)
	# Copy index.html file from source code folder to the web folder
	staticFiles = ["index.html", "jquery.js"]
	for s in staticFiles: shutil.copy2(installPath + "/" + s, webPath + "/" + s)
	if args.html: sys.exit()
	
	# Check in the FITS path for a file containing 
	
	fitsFiles = []
	# Find all folders in data path
	folders = os.walk(rootPath)
	
	FITSFilenames = []
	for f in folders:
		if debug: print("Folder: %s"%f[0])
		for file in f[2]:
			m = search_re.match(file)
			if (m): 
				FITSFilenames.append(file)

		print ("Found %d fits files in the folder %s"%(len(FITSFilenames), f[0]))
		
	jsonData = []

	for index, f in enumerate(FITSFilenames):
		newImage = imageObject()
		if (newImage.initFromFITSFile(f, path=rootPath)==False): continue
		imageJSON = {}
		if not skipimages:
			imageFilename = imageFolder + "/" + changeExtension(newImage.filename, "png")
			if not os.path.exists(imageFilename) or forceImages:
				newImage.writeAsPNG(boosted=True, filename=imageFilename)
			else:
				if debug: print "Image exists, not overwriting."
			imageJSON['pngFilename'] = "images/" + changeExtension(newImage.filename, "png")
		imageFilename = imageFolder + "/thumb_" + changeExtension(newImage.filename, "png")
		if not os.path.exists(imageFilename) or forceImages:
			newImage.createThumbnail(filename=imageFilename, size=thumbnailSize)
		else:
			if debug: print "Thumbnail exists. Not overwriting."
		imageJSON['thumbnailFilename'] = "images/thumb_" + changeExtension(newImage.filename, "png")
		imageJSON['sourceFilename'] = newImage.filename
		imageJSON['xSize'] = newImage.size[0]
		imageJSON['ySize'] = newImage.size[1]
		jsonData.append(imageJSON)
		progressPercent = float(index+1) / float(len(FITSFilenames)) * 100.
		if not debug:
			sys.stdout.write("\rProgress:  %3.1f%%, %d of %d files,"%(progressPercent, index+1, len(FITSFilenames)))
			sys.stdout.flush()
		else:
			print "Progress:  %3.1f%%, %d of %d files,"%(progressPercent, index+1, len(FITSFilenames))
		
	if not debug:
		sys.stdout.write("\n")
		sys.stdout.flush()	
	
	jsFilename = webPath + "/imageMetadata.js"
	jsFile = open(jsFilename, 'wt')
	jsFile.write("var allImages= ")
	jsFile.write(json.dumps(jsonData))
	jsFile.write(";")
	jsFile.close()
	
	
	print ""
	print "Finished!"
	print "Point your browser at: %s"%("file://" + webPath + "/index.html")
