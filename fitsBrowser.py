import collections
import datetime
import argparse, sys, os, re, json, shutil, fcntl
import configHelper, numpy
import astropy
import scipy.ndimage
import scipy.misc
from astropy.io import fits
from PIL import Image,ImageDraw,ImageFont

debug = False
fh=0

def  run_once():
     global  fh
     fh=open(os.path.realpath(__file__),'r')
     print "Trying to run_once"
     try:
         fcntl.flock(fh,fcntl.LOCK_EX|fcntl.LOCK_NB)
     except:
         os._exit(0)

class imageObject:
	def __init__(self):
		self.filename = None
		self.boostedImageExists = False
		self.allHeaders = {}
		self.fullImage = {}
		
	def initFromFITSFile(self, filename, path="."):
		images = []
		try:
			hdulist = fits.open(path + "/" + filename)
			if debug: print "Info: ", hdulist.info()
			# card = hdulist[0]
			for h in hdulist:
				if type(h.data) is numpy.ndarray:
					imageObject = {}
					imageObject['data'] = h.data
					imageObject['size'] = numpy.shape(h.data)
					images.append(imageObject)
					if debug: print("Found image data of dimensions (%d, %d)"%(imageObject['size'][0], imageObject['size'][1]))
				else:
					if debug: print "This card has no image data"
					continue                 # This card has no image data
			# Grab all of the FITS headers I can find
			for card in hdulist:
				for key in card.header.keys():
					self.allHeaders[key] = card.header[key]
			hdulist.close(output_verify='ignore')
		except astropy.io.fits.verify.VerifyError as e:
			
			print "WARNING: Verification error", e
			
		except: 
			print "Unexpected error:", sys.exc_info()[0]
			print "Could not find any valid FITS data for %s"%filename
			return False
		
		self.filename = filename
		if len(images)==0:
			if debug: print "Could not find any valid FITS data for %s"%filename
			return False
		if len(images)>1:
			self.combineImages(images)
		else:
			self.fullImage = images[0]
			self.size = numpy.shape(self.fullImage['data'])
		return True
		
	def getHeader(self, key):
		if key in self.allHeaders.keys():
			return { key: self.allHeaders[key] }
			
	def combineImages(self, images):
		if debug: print "Combining %d multiple images."%len(images)
		WFC = False
		try:
			instrument = self.allHeaders['INSTRUME']
			WFC = True
		except KeyError:
			pass
		
		# Reduce the images sizes by 1/4	
		for num, i in enumerate(images):
			percent = 25
			if debug: print "Shrinking image %d by %d percent."%(num, percent)
			i['data'] = scipy.misc.imresize(self.boostImageData(i['data']), percent)
			i['size'] = numpy.shape(i['data'])
			if debug: print "New size:", i['size']
			
		if WFC:
			# Custom code to stitch the WFC images together
			CCD1 = images[0]
			CCD2 = images[1]
			CCD3 = images[2]
			CCD4 = images[3]
			width = CCD1['size'][1]
			height = CCD1['size'][0] 
			fullWidth = width + height
			fullHeight = 3 * width
			if debug: print "WFC width", fullWidth, "WFC height", fullHeight
			fullImage = numpy.zeros((fullHeight, fullWidth))
			CCD3data = numpy.rot90(CCD3['data'], 3)
			fullImage[0:width, width:width+height] = CCD3data
			CCD2data = CCD2['data']
			fullImage[width:width+height, 0:width] = CCD2data
			CCD4data = numpy.rot90(CCD4['data'], 3)
			fullImage[width:2*width, width:width+height] = CCD4data
			CCD1data = numpy.rot90(CCD1['data'], 3)
			fullImage[2*width:3*width, width:width+height] = CCD1data
			fullImage = numpy.rot90(fullImage, 2)
		else:
			totalWidth = 0
			totalHeight = 0
			for i in images:
				totalWidth+= i['size'][1]
				totalHeight+=i['size'][0]
			if debug: print "potential width, height", totalWidth, totalHeight 
			if totalWidth<totalHeight:
				if debug: print "Stacking horizontally"
				maxHeight = 0
				for i in images:
					if i['size'][0]>maxHeight: maxHeight = i['size'][0]
				fullImage = numpy.zeros((maxHeight, totalWidth))
				if debug: print "Full image shape", numpy.shape(fullImage)
				segWstart = 0
				segHstart = 0
				for num, i in enumerate(images):
					segWidth = i['size'][1] 
					segHeight = i['size'][0]
					segWend = segWstart + segWidth
					segHend = segHstart + segHeight
					fullImage[segHstart:segHend, segWstart: segWend] = i['data']
					segWstart+= segWidth
		
		
		self.fullImage['data'] = fullImage
		self.fullImage['size'] = numpy.shape(fullImage)
		self.size = numpy.shape(fullImage)
		if debug: print "Final size:", self.size
		
	def boostImageData(self, imageData):
		""" Returns a normalised array where lo percent of the pixels are 0 and hi percent of the pixels are 255 """
		hi = 99
		lo = 20
		data = imageData
		max = data.max()
		dataArray = data.flatten()
		pHi = numpy.percentile(dataArray, hi)
		pLo = numpy.percentile(dataArray, lo)
		range = pHi - pLo
		scale = range/255
		data = numpy.clip(data, pLo, pHi)
		data-= pLo
		data/=scale
		return data
		
	
	def getBoostedImage(self):
		""" Returns a normalised array where lo percent of the pixels are 0 and hi percent of the pixels are 255 """
		hi = 99
		lo = 20
		imageData = self.fullImage['data']
		data = numpy.copy(self.fullImage['data'])
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
		imageData = numpy.copy(self.fullImage['data'])
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

def readHeaderListFile(filename):
	headerListFile = open(filename, 'rt')
	headers = []
	for line in headerListFile:
		line = line.strip()
		if len(line)==0: continue   # The line is blank
		if line[0]=='#': continue   # The line is comment
		headers.append(line)
	print "Will search for the following FITS headers:", headers
	headerListFile.close()
	return headers
			
	
def changeExtension(filename, extension):
	return os.path.splitext(filename)[0] + "." + extension 
	
if __name__ == "__main__":
	# run_once()
	parser = argparse.ArgumentParser(description='Makes a web-browser accessible page containing previews and thumbnails of all FITS images in a directory.')
	parser.add_argument('--datapath', type=str, help='Path where the FITS files are. Default: current directory')
	parser.add_argument('--webpath', type=str, help='Path to write the web page and images to. Default: current directory')
	parser.add_argument('--installpath', type=str, help='Path of where this application has been installed. This is so that it can find the HTML files to copy to the web folder. ')
	parser.add_argument('--size', type=int, help='Thumbnail size. Default is 128 pixels.')
	parser.add_argument('--save', action="store_true", help='Write the input parameters to the config file as default values.')
	parser.add_argument('--skipallimages', action="store_true", help="Skip creating of the images and thumbnails, just create the metadata. (For debugging purposes)")
	parser.add_argument('--skipimages', action="store_true", help="Skip creating of the images (but still creates the thumbnails.")
	parser.add_argument('--html', action="store_true", help="Skip most of the work and just write the HTML pages to the destination folder.")
	parser.add_argument('-f', '--force', action="store_true", help="Force the re-creation of the PNG images and thumbnails. The default behaviour is to check the output folder to see if the PNG image already exists. If so, it skips the creation step. ")
	parser.add_argument('--debug', action="store_true", help="Show some debug information.")
	parser.add_argument('--headerlist', type=str, help='Filename of a text file containing FITS headers that should be displayed on the web page.')
	parser.add_argument('-n', '--number', type=int, default=0, help='Stop after processing ''--number'' images. Default is process all images.')
	parser.add_argument('-t', '--title', type=str, default="FITS Image browser for {today}", help='Title for the web page. Use {today} as an alias for today\'s date and {folder} for the source folder name.')
	
	args = parser.parse_args()
	if args.debug: debug = True
	if debug: print(args)
	
	forceImages = False
	if args.force: forceImages = True
	
	searchForHeaders = False
	skipthumbnails = False
	skipimages = False
	processAllImages = True
	if args.number>0: 	processAllImages=False
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
		"ThumbnailSize": 128, 
		"FITSHeadersList": "/home/rashley/fitHeaders.list"
	}
	config.setDefaults(configDefaults)
	rootPath = config.assertProperty("FITSPath", args.datapath)
	searchString = config.assertProperty("SearchString", None)
	webPath = config.assertProperty("WebPath", args.webpath)
	installPath = config.assertProperty("InstallPath", args.installpath)
	thumbnailSize = config.assertProperty("ThumbnailSize", args.size)
	fitsHeaderListFilename = config.assertProperty("FITSHeadersList", args.headerlist)
	if args.save:
		config.save()
	
	print "Install path:", installPath
	if installPath == "undefined": 
		print "Please specify the install path of fitsBrowser. Use the --installpath command option, or specify it in ~/.config/fitsBrowser/fitsBrowser.conf file."
		sys.exit(-1)
	
	if os.path.exists(fitsHeaderListFilename):
		print "Loading a list file."
		headers = readHeaderListFile(fitsHeaderListFilename)
		if len(headers) > 0: searchForHeaders = True
		
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
	
	fitsFiles = []
	# Find all folders in data path
	folders = os.walk(rootPath)
	subFolders = []
	FITSFilenames = []
	for f in folders:
		if debug: print("Folder: %s"%os.path.realpath(f[0]))
		subFolders.append(os.path.realpath(f[0]))
		for file in f[2]:
			m = search_re.match(file)
			if (m): 
				FITSFilenames.append(file)

	
	print "subFolders:", subFolders
	mainFolderName = subFolders[0].split('/')
	print "Main folder:", mainFolderName[-1]
	print ("Found %d fits files to process."%len(FITSFilenames))
		
	jsonData = []

	for index, f in enumerate(FITSFilenames):
		if debug: print "Filename:", f
		if not processAllImages and ((index)==args.number): break
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
		if searchForHeaders:
			headerObject = collections.OrderedDict()
			for h in headers:
				try:
					headerObject.update(newImage.getHeader(h))
				except:
					print "No header data for", h
			imageJSON['headers'] = headerObject
				
		
		
		jsonData.append(imageJSON)
		progressPercent = float(index+1) / float(len(FITSFilenames)) * 100.
		if not debug:
			sys.stdout.write("\rProgress:  %3.1f%%, %d of %d files. %s        "%(progressPercent, index+1, len(FITSFilenames), f))
			sys.stdout.flush()
		else:
			print "%s \tProgress:  %3.1f%%, %d of %d files."%(f, progressPercent, index+1, len(FITSFilenames))
		
	if not debug:
		sys.stdout.write("\n")
		sys.stdout.flush()	
	
	titleString = args.title
	today = str(datetime.date.today()).replace('-','')
	print "rootPath", rootPath
	folder = str(os.path.dirname(os.path.realpath(rootPath)))
	print "Folder:", folder
	titleString = titleString.format(today = today, folder = folder)
	jsFilename = webPath + "/imageMetadata.js"
	jsFile = open(jsFilename, 'wt')
	jsFile.write('var title= "%s";\n'%titleString)
	jsFile.write("var allImages= ")
	jsFile.write(json.dumps(jsonData, sort_keys=False))
	jsFile.write(";\n")
	jsFile.close()
	
	
	print ""
	print "Finished!"
	print "Point your browser at: %s"%("file://" + webPath + "/index.html")
